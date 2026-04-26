-- Decoration set category restrictions
-- NULL or empty array = all categories allowed
-- Array of category IDs = restrict to those categories only
ALTER TABLE decoration_sets ADD COLUMN IF NOT EXISTS allowed_categories UUID[] DEFAULT NULL;
