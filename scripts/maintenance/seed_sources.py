import os
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase: Client = create_client(url, key)

sources = [
    {
        "jurisdiction_id": "san-jose",
        "url": "https://sanjose.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "San Jose Agendas",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "agenda",
            "title": "San Jose Agendas",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "san-jose",
        "url": "https://sanjose.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "San Jose Agenda Packets",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "agenda_packet",
            "title": "San Jose Agenda Packets",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "san-jose",
        "url": "https://sanjose.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "San Jose Attachments",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "attachment",
            "title": "San Jose Attachments",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "san-jose",
        "url": "https://sanjose.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "San Jose Staff Reports",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "staff_report",
            "title": "San Jose Staff Reports",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "san-jose",
        "url": "https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
        "type": "code",
        "name": "San Jose Municipal Code",
        "status": "active",
        "source_method": "scrape",
        "handler": "municode",
        "metadata": {
            "document_type": "municipal_code",
            "title": "San Jose Municipal Code",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "santa-clara-county",
        "url": "https://sccgov.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Santa Clara County Agendas",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "agenda",
            "title": "Santa Clara County Agendas",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "santa-clara-county",
        "url": "https://sccgov.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Santa Clara County Agenda Packets",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "agenda_packet",
            "title": "Santa Clara County Agenda Packets",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "santa-clara-county",
        "url": "https://sccgov.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Santa Clara County Attachments",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "attachment",
            "title": "Santa Clara County Attachments",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "santa-clara-county",
        "url": "https://sccgov.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Santa Clara County Staff Reports",
        "status": "active",
        "source_method": "scrape",
        "handler": "legistar_calendar",
        "metadata": {
            "document_type": "staff_report",
            "title": "Santa Clara County Staff Reports",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "saratoga",
        "url": "https://www.saratoga.ca.us/AgendaCenter",
        "type": "meetings",
        "name": "Saratoga Agenda Center",
        "status": "active",
        "source_method": "scrape",
        "handler": "agenda_center",
        "metadata": {
            "document_type": "agenda",
            "title": "Saratoga Agenda Center",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "saratoga",
        "url": "https://www.saratoga.ca.us/AgendaCenter",
        "type": "meetings",
        "name": "Saratoga Agenda Packets",
        "status": "active",
        "source_method": "scrape",
        "handler": "agenda_center",
        "metadata": {
            "document_type": "agenda_packet",
            "title": "Saratoga Agenda Packets",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "saratoga",
        "url": "https://www.saratoga.ca.us/AgendaCenter",
        "type": "meetings",
        "name": "Saratoga Attachments",
        "status": "active",
        "source_method": "scrape",
        "handler": "agenda_center",
        "metadata": {
            "document_type": "attachment",
            "title": "Saratoga Attachments",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "saratoga",
        "url": "https://www.saratoga.ca.us/AgendaCenter",
        "type": "meetings",
        "name": "Saratoga Staff Reports",
        "status": "active",
        "source_method": "scrape",
        "handler": "agenda_center",
        "metadata": {
            "document_type": "staff_report",
            "title": "Saratoga Staff Reports",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "sunnyvale",
        "url": "https://sunnyvaleca.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Sunnyvale Agendas",
        "status": "active",
        "source_method": "scrape",
        "handler": "sunnyvale_agendas",
        "metadata": {
            "document_type": "agenda",
            "title": "Sunnyvale Agendas",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "sunnyvale",
        "url": "https://sunnyvaleca.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Sunnyvale Agenda Packets",
        "status": "active",
        "source_method": "scrape",
        "handler": "sunnyvale_agendas",
        "metadata": {
            "document_type": "agenda_packet",
            "title": "Sunnyvale Agenda Packets",
            "trust_tier": "official_partner",
        },
    },
    {
        "jurisdiction_id": "sunnyvale",
        "url": "https://sunnyvaleca.legistar.com/Calendar.aspx",
        "type": "meetings",
        "name": "Sunnyvale Attachments",
        "status": "active",
        "source_method": "scrape",
        "handler": "sunnyvale_agendas",
        "metadata": {
            "document_type": "attachment",
            "title": "Sunnyvale Attachments",
            "trust_tier": "official_partner",
        },
    },
]

for source in sources:
    try:
        # Check if exists
        existing = supabase.table("sources").select("id").eq("url", source["url"]).execute()
        if existing.data:
            print(f"Skipping {source['url']} (already exists)")
        else:
            data = supabase.table("sources").insert(source).execute()
            print(f"Inserted {source['url']}")
    except Exception as e:
        print(f"Error inserting {source['url']}: {e}")
