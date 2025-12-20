#!/usr/bin/env python3
"""Run schema migration 004 to fix legislation table."""
import os
import psycopg2

def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return 1
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Running migration 004_fix_legislation_schema...")
    
    # Add missing columns
    cur.execute("ALTER TABLE legislation ADD COLUMN IF NOT EXISTS description TEXT;")
    cur.execute("ALTER TABLE legislation ADD COLUMN IF NOT EXISTS file_number TEXT;")
    
    # Check if rename needed
    cur.execute("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='legislation' AND column_name='text'
        ) AND NOT EXISTS(
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='legislation' AND column_name='text_content'
        );
    """)
    needs_rename = cur.fetchone()[0]
    
    if needs_rename:
        cur.execute("ALTER TABLE legislation RENAME COLUMN text TO text_content;")
        print("Renamed 'text' to 'text_content'")
    
    conn.commit()
    print("Migration successful!")
    
    # Verify
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='legislation' ORDER BY ordinal_position;")
    print("Columns:", [row[0] for row in cur.fetchall()])
    
    conn.close()
    return 0

if __name__ == "__main__":
    exit(main())
