import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from neo4j import GraphDatabase
from shared.config import settings

logger = logging.getLogger("orqix.shared.db")

# Detect SQLite to adjust engine settings
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        settings.DATABASE_URL, 
        pool_pre_ping=True, 
        pool_size=10, 
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Neo4j Client Wrapper
class Neo4jClient:
    def __init__(self):
        self._driver = None

    def connect(self):
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def execute_query(self, query: str, parameters: dict = None):
        if not self._driver:
            self.connect()
        if not self._driver:
            logger.warning("Neo4j driver not connected. Skipping graph write.")
            return []
        
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

neo4j_client = Neo4jClient()
