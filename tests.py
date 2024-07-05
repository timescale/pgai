
import unittest
from testcontainers.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.waiting_utils import wait_for_logs
import psycopg2
import requests


class TestPLPython3UFunctionWithProxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Define the Docker image name and tag
        image_name = "my_python_app"
        image_tag = "latest"
        tag = f"{image_name}:{image_tag}"

        # Build the Docker image
        import docker
        client = docker.from_env()
        client.images.build(path=".", tag=tag)

        # Create a custom Docker network
        cls.network = Network()
        cls.network.create()

        # Start MockServer container in the custom network
        cls.mockserver = DockerContainer("mockserver/mockserver", network=cls.network.name)
        cls.mockserver.with_exposed_ports(1080)
        cls.mockserver.start()
        wait_for_logs(cls.mockserver, "started on port")

        name = cls.mockserver.get_wrapped_container().name

        # Get the MockServer internal network URL
        cls.mockserver_internal_url = f"http://{name}:1080"

        # Configure MockServer expectations
        cls.configure_mockserver()

        # Start PostgreSQL container in the custom network
        cls.postgres = PostgresContainer(tag, network=cls.network.name)
        cls.postgres.with_env("CO_API_URL", cls.mockserver_internal_url)
        cls.postgres.start()
        wait_for_logs(cls.postgres, "database system is ready to accept connections")

        print("starting pg container")
        # Connect to the PostgreSQL container
        cls.connection = psycopg2.connect(
            dbname='test',
            user='test',
            password='test',
            host=cls.postgres.get_container_host_ip(),
            port=cls.postgres.get_exposed_port(5432)
        )
        cls.cursor = cls.connection.cursor()

        # Create the PL/Python function
        cls.create_plpython_function()

    @classmethod
    def tearDownClass(cls):
        # Close the database connection
        cls.cursor.close()
        cls.connection.close()

        # Stop the containers and remove the network
        cls.postgres.stop()
        cls.mockserver.stop()
        cls.network.remove()

    @classmethod
    def configure_mockserver(cls):
        expectation = {
            "httpRequest": {
                "method": "POST",
                "path": "/chat",
                "body": {
                    "message": "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
                    "model": "command-r-plus",
                    "seed": 42,
                    "stream": False
                }
            },
            "httpResponse": {
                "statusCode": 200,
                "headers": {
                    "num_chars": ["484"],
                    "num_tokens": ["121"],
                    "Content-Type": ["application/json"]
                },
                "body": {
                    "json": {
                        "response_id": "55814a42-ceda-43b0-88f7-a82b693363b4",
                        "text": "According to a tongue-twister poem often attributed to Robert Hobart Davis and Richard Wayne Peck, a woodchuck (also known as a groundhog) would chuck \"as much wood as a woodchuck would, if a woodchuck could chuck wood.\" \n\nIn a more practical sense, a real-life woodchuck might gather and move a few pounds of wood or soil when building its burrow, but they primarily feed on plants, grasses, fruits, and vegetables, rather than \"chucking\" large amounts of wood.",
                        "generation_id": "65586b16-1263-484d-9d20-19b1b885e3c6",
                        "chat_history": [],
                        "finish_reason": "COMPLETE",
                        "meta": {
                            "api_version": {"version": "1"},
                            "billed_units": {"input_tokens": 16, "output_tokens": 105},
                            "tokens": {"input_tokens": 82, "output_tokens": 105}
                        }
                    }

                }
            }
        }

        host_ip = cls.mockserver.get_container_host_ip()
        print(f"Host {host_ip}")
        host_port = cls.mockserver.get_exposed_port(1080)
        print(f"Port {host_port}")

        requests.put(f"http://{host_ip}:{host_port}/mockserver/expectation", json=expectation)

    @ classmethod
    def create_plpython_function(cls):
        cls.cursor.execute("CREATE EXTENSION IF NOT EXISTS plpython3u;")
        cls.cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cls.cursor.execute("CREATE EXTENSION IF NOT EXISTS ai;")
        cls.connection.commit()

    def test_get_http_data(self):
        # Call the PL/Python function
        self.cursor.execute("""
SELECT cohere_chat_complete(
'command-r-plus'
, 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
, _api_key => 'asdf'
, _seed=>42
)->>'text'
;
""")
        result = self.cursor.fetchone()[0]
        # Assert that the function returned the mocked response
        expected = "According to a tongue-twister poem often attributed to Robert Hobart Davis and Richard Wayne Peck, a woodchuck (also known as a groundhog) would chuck \"as much wood as a woodchuck would, if a woodchuck could chuck wood.\" \n\nIn a more practical sense, a real-life woodchuck might gather and move a few pounds of wood or soil when building its burrow, but they primarily feed on plants, grasses, fruits, and vegetables, rather than \"chucking\" large amounts of wood."

        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
