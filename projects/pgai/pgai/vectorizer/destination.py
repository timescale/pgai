from typing import Literal, Protocol, Sequence

from psycopg import sql
from pydantic import BaseModel


class DestinationProtocol(Protocol):
    """Protocol that all destination implementations must follow"""
    implementation: str
    
    def get_target_table_ident(self, source_schema: str, source_table: str) -> sql.Identifier:
        """Returns the SQL identifier for the target table"""
        ...
        
    def get_delete_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed, 
        placeholders: sql.Composed
    ) -> sql.Composed:
        """Returns a SQL query to delete existing embeddings"""
        ...
        
    def get_copy_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed
    ) -> sql.Composed:
        """Returns a SQL query for COPY operation to insert embeddings"""
        ...
        
    def should_use_copy(self) -> bool:
        """Returns whether to use COPY or UPDATE for writing embeddings"""
        ...


class DefaultDestination(BaseModel):
    implementation: Literal["default"]
    target_schema: str
    target_table: str
    
    def get_target_table_ident(self, source_schema: str, source_table: str) -> sql.Identifier:
        """Returns the SQL identifier for the target table (schema.table)"""
        return sql.Identifier(self.target_schema, self.target_table)
    
    def get_delete_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed, 
        placeholders: sql.Composed
    ) -> sql.Composed:
        """Returns a SQL query to delete existing embeddings from the target table"""
        return sql.SQL("DELETE FROM {} WHERE ({}) IN ({})").format(
            target_table_ident,
            pk_fields_sql,
            placeholders,
        )
    
    def get_copy_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed
    ) -> sql.Composed:
        """Returns a SQL query for COPY operation to insert embeddings into the target table"""
        return sql.SQL(
            "COPY {} ({}, chunk_seq, chunk, embedding) FROM STDIN WITH (FORMAT BINARY)"
        ).format(
            target_table_ident,
            pk_fields_sql,
        )
    
    def should_use_copy(self) -> bool:
        """Default destination always uses COPY"""
        return True


class SourceDestination(BaseModel):
    implementation: Literal["source"]
    embedding_column: str
    
    def get_target_table_ident(self, source_schema: str, source_table: str) -> sql.Identifier:
        """Returns the SQL identifier for the source table as target (schema.table)"""
        return sql.Identifier(source_schema, source_table)
    
    def get_delete_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed, 
        placeholders: sql.Composed
    ) -> sql.Composed:
        """Returns a SQL query to update the embedding column to NULL"""
        return sql.SQL("UPDATE {} SET {} = NULL WHERE ({}) IN ({})").format(
            target_table_ident,
            sql.Identifier(self.embedding_column),
            pk_fields_sql,
            placeholders,
        )
    
    def get_copy_embeddings_query(
        self, 
        target_table_ident: sql.Identifier, 
        pk_fields_sql: sql.Composed
    ) -> sql.Composed:
        """SourceDestination doesn't use COPY, uses UPDATE instead"""
        return sql.SQL("")  # Placeholder, not actually used
    
    def should_use_copy(self) -> bool:
        """SourceDestination uses UPDATE instead of COPY"""
        return False
        
    def get_update_embedding_query(
        self,
        target_table_ident: sql.Identifier,
        pk_fields_sql: sql.Composed,
        pk_fields: Sequence[sql.Identifier]
    ) -> sql.Composed:
        """Returns a SQL query to update the embedding column with the embedding value"""
        return sql.SQL("UPDATE {} SET {} = %s WHERE ({}) = ({})").format(
            target_table_ident,
            sql.Identifier(self.embedding_column),
            pk_fields_sql,
            sql.SQL(", ").join([sql.Placeholder() for _ in pk_fields])
        )
