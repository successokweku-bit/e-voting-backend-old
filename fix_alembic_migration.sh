#!/bin/bash
# Fix Alembic migration for secure voting tables
# Run this script to resolve the duplicate table error

echo "🔧 Fixing Alembic Migration for Secure Voting Tables"
echo "======================================================"
echo ""

# Step 1: Check current migration status
echo "Step 1: Checking current migration status..."
alembic current
echo ""

# Step 2: Mark the failed migration as complete (if it partially ran)
echo "Step 2: The migration failed because 'audit_logs' already exists."
echo "This means some tables were created but not all."
echo ""
echo "We have 3 options:"
echo ""
echo "Option 1: Mark the migration as complete and create missing tables manually"
echo "Option 2: Delete the failed migration and create a new fixed one"
echo "Option 3: Rollback and try again"
echo ""

read -p "Enter your choice (1/2/3): " choice

case $choice in
  1)
    echo ""
    echo "Option 1: Marking migration as complete..."
    echo ""
    echo "Run this SQL in your database:"
    echo "--------------------------------------------"
    echo "-- Mark the migration as complete"
    echo "UPDATE alembic_version SET version_num = '88ef675becd8';"
    echo ""
    echo "-- Then create missing tables manually:"
    echo "-- (Copy the SQL from the migration file for tables that don't exist)"
    echo "--------------------------------------------"
    ;;
    
  2)
    echo ""
    echo "Option 2: Creating fixed migration..."
    echo ""
    
    # Rollback the failed migration
    echo "Rolling back failed migration..."
    alembic downgrade -1
    
    # Delete the problematic migration file
    echo "Deleting problematic migration file..."
    MIGRATION_FILE=$(ls alembic/versions/*_add_secure_voting.py 2>/dev/null)
    if [ -f "$MIGRATION_FILE" ]; then
        echo "Found: $MIGRATION_FILE"
        read -p "Delete this file? (y/n): " confirm
        if [ "$confirm" == "y" ]; then
            rm "$MIGRATION_FILE"
            echo "Deleted"
        fi
    fi
    
    echo ""
    echo "Now create a new migration with the fixed code:"
    echo "alembic revision -m 'add secure voting tables fixed'"
    echo ""
    echo "Then replace the content with the code from 'Fix Migration' artifact"
    ;;
    
  3)
    echo ""
    echo "🔙 Option 3: Rolling back..."
    echo ""
    alembic downgrade -1
    echo ""
    echo "Rolled back. Now you can run 'alembic upgrade head' again"
    ;;
    
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

echo ""
echo "======================================================"
echo "Next steps in the README below"