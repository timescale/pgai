import weakref

from sqlalchemy import Column, ForeignKey, Integer, String, inspect, text
from sqlalchemy.orm import backref, declarative_base, relationship

Base = declarative_base()

def create_dynamic_tables(engine, parent_class, field_names):
    """Create tables outside the descriptor using raw SQL"""
    for field_name in field_names:
        table_name = f"{parent_class.__tablename__}_{field_name.lower()}"
        create_table_sql = text(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER NOT NULL PRIMARY KEY,
            value VARCHAR,
            {parent_class.__tablename__}_id INTEGER,
            FOREIGN KEY({parent_class.__tablename__}_id) REFERENCES {parent_class.__tablename__} (id)
        )
        """)
        with engine.connect() as conn:
            conn.execute(create_table_sql)
            conn.commit()

class DynamicModelDescriptor:
    """
    A descriptor that lazily creates a related model and relationship
    when first accessed.
    """
    def __init__(self, base_class=Base):
        self.base_class = base_class
        self._created_model = None
        self._initialized = False

    def create_dynamic_model(self, parent_class):
        """Creates a new model class dynamically"""
        if self._created_model is not None:
            return self._created_model

        model_name = f"{parent_class.__name__}{self.field_name.capitalize()}"
        table_name = f"{parent_class.__tablename__}_{self.field_name.lower()}"

        # Create the model class
        new_model = type(
            model_name,
            (self.base_class,),
            {
                "__tablename__": table_name,
                "id": Column(Integer, primary_key=True),
                "value": Column(String),
                f"{parent_class.__tablename__}_id": Column(
                    Integer,
                    ForeignKey(f"{parent_class.__tablename__}.id")
                )
            }
        )

        # Add the relationship to the parent class
        rel = relationship(
            new_model,
            collection_class=list,
            backref=backref("parent", lazy="joined"),
            lazy="joined"
        )
        setattr(parent_class, f"{self.field_name}_collection", rel)

        self._created_model = new_model

        return new_model

    def __set_name__(self, owner, name):
        self.field_name = name

    def __get__(self, instance, owner):
        if not self._initialized:
            model = self.create_dynamic_model(owner)
            self._initialized = True
            return model
        if instance is None and self._initialized:
            return self._created_model

        return getattr(instance, f"{self.field_name}_collection")

    def __set__(self, instance, value):
        if not self._initialized:
            self.create_dynamic_model(instance.__class__)
            self._initialized = True

        collection = getattr(instance, f"{self.field_name}_collection")

        # Clear existing items
        collection.clear()

        # Add new values
        if isinstance(value, (list, tuple)):
            for val in value:
                new_item = self._created_model(value=str(val))
                collection.append(new_item)
        else:
            new_item = self._created_model(value=str(value))
            collection.append(new_item)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)

    tags = DynamicModelDescriptor()
    categories = DynamicModelDescriptor()


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Set echo=True to see SQL queries
    engine = create_engine("sqlite:///:memory:", echo=True)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)

    # Create the dynamic tables before using the models
    create_dynamic_tables(engine, User, ["tags", "categories"])

    Session = sessionmaker(bind=engine)
    session = Session()

    # Create a user and add some data
    user = User(name="John")
    session.add(user)
    session.commit()

    _ = user.tags
    _ = user.categories
    #session.commit()

    # Clear the session to ensure fresh loading
    session.expunge_all()

    print("\nTesting eager loading - should see JOIN in the query:")
    # This query should generate a single SQL statement with JOINs
    loaded_user = session.query(User).filter_by(name="John").first()

    print("\nAccessing relationships - should NOT generate additional queries:")
    print("Tags:", [tag.value for tag in loaded_user.tags])
    print("Categories:", [cat.value for cat in loaded_user.categories])

    # Alternative test using explicit joins
    print("\nTesting explicit joins:")
    UserTag = User.tags
    UserCategory = User.categories

    result = session.query(User). \
        join(UserTag). \
        join(UserCategory). \
        filter(User.name == "John"). \
        first()

    #print("User data loaded with explicit joins:")
    #print("Tags:", [tag.value for tag in result.tags])
    #print("Categories:", [cat.value for cat in result.categories])