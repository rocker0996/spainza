"""Production API package."""

"""Legacy PostgreSQL prototype API.

Current production entry point is ``wsgi.py`` -> ``backend/app.py`` and uses
SQLite storage under ``/app/database``. Keep this package out of deployment
routing unless a dedicated PostgreSQL migration is implemented.
"""
