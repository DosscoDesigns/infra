-- RCC Gear Sale - Spring 2026
-- Event + price rules + product mappings
-- Source: Merch Sale Price List.docx

-- 1. Create the event
INSERT INTO events (org_id, event_code, name, active)
SELECT o.id, 'RCC-GS-2604', 'RCC Gear Sale - Spring 2026', true
FROM orgs o WHERE o.org_code = 'RCC'
ON CONFLICT DO NOTHING;

-- 2. Create price rules (category-level descriptions, product-specific via price_rule_products)
-- Using a DO block so we can reference the event/org IDs

DO $$
DECLARE
  v_org_id UUID;
  v_event_id UUID;
  v_rule_id UUID;
BEGIN
  SELECT id INTO v_org_id FROM orgs WHERE org_code = 'RCC';
  SELECT id INTO v_event_id FROM events WHERE event_code = 'RCC-GS-2604';

  IF v_org_id IS NULL OR v_event_id IS NULL THEN
    RAISE NOTICE 'RCC org or Spring 2026 event not found — skipping price rules';
    RETURN;
  END IF;

  -- Tees - $15
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Tees', 15.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('DM130', 'DM130L', 'DM1350L', 'DT1350', 'DT137L', 'DT153', 'DT151', 'NL5030', 'BC3001CVC', 'ST350', 'ST420', 'DT5300', 'PC54', 'PC54Y', '29B', 'CAR54T', 'DT130Y');

  -- Long Sleeve Tees - $18
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Long Sleeve Tees', 18.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('DM132', 'DT132L', 'ST350LS', 'YST420LS');

  -- Polo - Electric Heather - $25
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Polo - Electric Heather', 25.00, 1, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'ST590';

  -- Polo - Sport-Wick/Pique - $30
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Polos', 30.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('ST650', 'K830', '1380-TSJ', '380-TSJ');

  -- Polo - OGIO - $45
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Ogio Polo', 45.00, 1, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'OG109';

  -- Fishing Shirt (Eddie Bauer) - $60
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Fishing Shirt', 60.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('EB602', 'EB600');

  -- UV Fishing Shirt - $40
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'UV Fishing Shirt', 40.00, 1, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'W961';

  -- Hoodie - $25
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Hoodie', 25.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('PC78H', 'PC90YH');

  -- Crewneck - $25
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Crewneck', 25.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'PC78';

  -- Zip Hoodie - $30
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Zip Hoodie', 30.00, 1, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'PC78ZH';

  -- V-Neck Sweatshirt - $25
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'V-Neck Sweatshirt', 25.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'LPC098V';

  -- Rain Jacket - $23
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Rain Jacket', 23.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'J344';

  -- Fleece Full-Zip Hoodie - $27
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Fleece Zip Hoodie', 27.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'DT8102';

  -- Microfleece Jacket - $35
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Microfleece Jacket', 35.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('F223', 'L223');

  -- Hats - $25
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Hats', 25.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('112', '115');

  -- Cardigan - $35
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Cardigan', 35.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('L807', 'L5430', 'LM1008');

  -- Blouse - Tunic/3-4 Sleeve - $35
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Blouse', 35.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code = 'LW701';

  -- Shorts - $15
  INSERT INTO price_rules (org_id, event_id, description, override_price, priority, active)
  VALUES (v_org_id, v_event_id, 'Shorts', 15.00, 0, true) RETURNING id INTO v_rule_id;
  INSERT INTO price_rule_products (price_rule_id, product_id)
  SELECT v_rule_id, p.id FROM products p WHERE p.style_code IN ('ST355', 'YST355');

END $$;
