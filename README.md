# DD Infrastructure

Supabase infrastructure for Dossco Designs platform.

## Setup

```bash
# Start Supabase
supabase start

# Apply migrations
supabase db reset

# Generate types
supabase gen types typescript --local > types/database.types.ts
```

## Environment

- **Local Supabase:** Port 55322
- **Database:** PostgreSQL with RLS policies
- **Storage:** File uploads for product images, decorations
- **Edge Functions:** API endpoints and webhooks

## Projects

This infrastructure supports:
- DD main platform (`~/dev/dd/dd`)
- Organization-specific stores
- Inventory management
- Decoration management
- Order processing

## Database Schema

- **Products & Variants:** Product catalog with SanMar integration
- **Decorations & Sets:** Design management for organizations
- **Organizations:** Client management and branding
- **Inventory:** Stock tracking and movement
- **Orders:** Customer order processing (coming soon)