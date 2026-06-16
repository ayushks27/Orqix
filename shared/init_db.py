from shared.db import engine, Base, SessionLocal
from shared.models import Organization, User, UserRole
from shared.auth import hash_password

def initialize_database():
    print("Initializing PostgreSQL tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
    
    db = SessionLocal()
    try:
        # Check if default org exists
        default_org = db.query(Organization).filter(Organization.id == "org_default").first()
        if not default_org:
            default_org = Organization(id="org_default", name="Orqix Labs")
            db.add(default_org)
            db.commit()
            print("Default organization 'org_default' created.")

        # Check and seed admin user
        admin_user = db.query(User).filter(User.email == "admin@orqix.ai").first()
        if not admin_user:
            admin = User(
                id="usr_admin",
                org_id="org_default",
                email="admin@orqix.ai",
                password_hash=hash_password("admin_pass"),
                role=UserRole.ADMIN
            )
            db.add(admin)
            print("Default Admin User seeded (admin@orqix.ai / admin_pass)")

        # Check and seed researcher user
        res_user = db.query(User).filter(User.email == "researcher@orqix.ai").first()
        if not res_user:
            researcher = User(
                id="usr_researcher",
                org_id="org_default",
                email="researcher@orqix.ai",
                password_hash=hash_password("researcher_pass"),
                role=UserRole.RESEARCHER
            )
            db.add(researcher)
            print("Default Researcher User seeded (researcher@orqix.ai / researcher_pass)")

        db.commit()
        print("Database seeding completed.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    initialize_database()
