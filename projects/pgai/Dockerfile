FROM python:3.12-slim

WORKDIR /build
COPY ./ /build/
RUN pip3 install -v --compile --root-user-action=ignore /build
WORKDIR /
RUN rm -r /build

ENV PATH=/usr/local/bin/:$PATH
ENTRYPOINT [ "vectorizer" ]
CMD ["--version"]
