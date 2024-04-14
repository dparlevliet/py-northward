# Path: migrations/20240410093809_migration.py
dependencies = [
    # List of dependencies
    'module1/migrations/20240410093757_migration'
]

def up():
    print("Hello, running up() from migration 20240410093809")

def down():
    print("Hello, running down() from migration 20240410093809")