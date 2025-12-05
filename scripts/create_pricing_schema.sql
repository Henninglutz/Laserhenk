-- ======================================================================
-- Pricing Schema für LASERHENK
-- ======================================================================
-- Erstellt ein flexibles Pricing-System basierend auf:
-- - Preiskategorien (preiskat 1-9 aus fabric metadata)
-- - Garment Types (suit, jacket, trousers, etc.)
-- - Aufschläge für Extras
-- ======================================================================

-- ======================================================================
-- 1. PRICING RULES TABLE
-- ======================================================================

CREATE TABLE IF NOT EXISTS pricing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Preiskategorie (aus fabrics.additional_metadata.preiskat)
    price_category VARCHAR(50) NOT NULL,

    -- Art des Kleidungsstücks
    garment_type VARCHAR(50) NOT NULL,

    -- Basispreis für dieses Kleidungsstück in dieser Kategorie
    base_price DECIMAL(10,2) NOT NULL,

    -- Optional: Preis pro Meter (falls relevant)
    price_per_meter DECIMAL(10,2),

    -- Beschreibung
    description TEXT,

    -- Gültigkeitszeitraum
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_pricing_rule UNIQUE(price_category, garment_type, valid_from),
    CONSTRAINT positive_price CHECK (base_price > 0)
);

-- Index für schnelle Lookups
CREATE INDEX idx_pricing_category_garment ON pricing_rules(price_category, garment_type);
CREATE INDEX idx_pricing_valid ON pricing_rules(valid_from, valid_until);

-- ======================================================================
-- 2. PRICING EXTRAS TABLE (Aufschläge)
-- ======================================================================

CREATE TABLE IF NOT EXISTS pricing_extras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Name des Extras
    extra_type VARCHAR(100) NOT NULL UNIQUE,

    -- Aufpreis
    extra_price DECIMAL(10,2) NOT NULL,

    -- Beschreibung
    description TEXT,

    -- Optional: Prozentual oder fix
    is_percentage BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT positive_extra_price CHECK (extra_price >= 0)
);

-- ======================================================================
-- 3. INITIAL DATA - PRICING RULES
-- ======================================================================

-- Preiskategorie 1-2: Entry Level
INSERT INTO pricing_rules (price_category, garment_type, base_price, description) VALUES
('1', 'suit', 1200.00, 'Entry Level - 2-Teiler Anzug'),
('1', 'three_piece', 1500.00, 'Entry Level - 3-Teiler Anzug'),
('1', 'jacket', 800.00, 'Entry Level - Sakko einzeln'),
('1', 'trousers', 400.00, 'Entry Level - Hose einzeln'),
('1', 'vest', 350.00, 'Entry Level - Weste einzeln'),
('1', 'coat', 1800.00, 'Entry Level - Mantel'),
('1', 'tuxedo', 1800.00, 'Entry Level - Smoking'),

('2', 'suit', 1350.00, 'Entry Level+ - 2-Teiler Anzug'),
('2', 'three_piece', 1650.00, 'Entry Level+ - 3-Teiler Anzug'),
('2', 'jacket', 875.00, 'Entry Level+ - Sakko einzeln'),
('2', 'trousers', 450.00, 'Entry Level+ - Hose einzeln'),
('2', 'vest', 375.00, 'Entry Level+ - Weste einzeln'),
('2', 'coat', 1950.00, 'Entry Level+ - Mantel'),
('2', 'tuxedo', 1950.00, 'Entry Level+ - Smoking'),

-- Preiskategorie 3-4: Standard
('3', 'suit', 1500.00, 'Standard - 2-Teiler Anzug'),
('3', 'three_piece', 1800.00, 'Standard - 3-Teiler Anzug'),
('3', 'jacket', 950.00, 'Standard - Sakko einzeln'),
('3', 'trousers', 500.00, 'Standard - Hose einzeln'),
('3', 'vest', 400.00, 'Standard - Weste einzeln'),
('3', 'coat', 2100.00, 'Standard - Mantel'),
('3', 'tuxedo', 2100.00, 'Standard - Smoking'),

('4', 'suit', 1650.00, 'Standard+ - 2-Teiler Anzug'),
('4', 'three_piece', 1950.00, 'Standard+ - 3-Teiler Anzug'),
('4', 'jacket', 1050.00, 'Standard+ - Sakko einzeln'),
('4', 'trousers', 550.00, 'Standard+ - Hose einzeln'),
('4', 'vest', 425.00, 'Standard+ - Weste einzeln'),
('4', 'coat', 2250.00, 'Standard+ - Mantel'),
('4', 'tuxedo', 2250.00, 'Standard+ - Smoking'),

-- Preiskategorie 5-6: Premium
('5', 'suit', 1800.00, 'Premium - 2-Teiler Anzug'),
('5', 'three_piece', 2100.00, 'Premium - 3-Teiler Anzug'),
('5', 'jacket', 1150.00, 'Premium - Sakko einzeln'),
('5', 'trousers', 600.00, 'Premium - Hose einzeln'),
('5', 'vest', 450.00, 'Premium - Weste einzeln'),
('5', 'coat', 2400.00, 'Premium - Mantel'),
('5', 'tuxedo', 2400.00, 'Premium - Smoking'),

('6', 'suit', 1950.00, 'Premium+ - 2-Teiler Anzug'),
('6', 'three_piece', 2250.00, 'Premium+ - 3-Teiler Anzug'),
('6', 'jacket', 1250.00, 'Premium+ - Sakko einzeln'),
('6', 'trousers', 650.00, 'Premium+ - Hose einzeln'),
('6', 'vest', 475.00, 'Premium+ - Weste einzeln'),
('6', 'coat', 2550.00, 'Premium+ - Mantel'),
('6', 'tuxedo', 2550.00, 'Premium+ - Smoking'),

-- Preiskategorie 7-8: High-End
('7', 'suit', 2100.00, 'High-End - 2-Teiler Anzug'),
('7', 'three_piece', 2400.00, 'High-End - 3-Teiler Anzug'),
('7', 'jacket', 1350.00, 'High-End - Sakko einzeln'),
('7', 'trousers', 700.00, 'High-End - Hose einzeln'),
('7', 'vest', 500.00, 'High-End - Weste einzeln'),
('7', 'coat', 2700.00, 'High-End - Mantel'),
('7', 'tuxedo', 2700.00, 'High-End - Smoking'),

('8', 'suit', 2250.00, 'High-End+ - 2-Teiler Anzug'),
('8', 'three_piece', 2550.00, 'High-End+ - 3-Teiler Anzug'),
('8', 'jacket', 1450.00, 'High-End+ - Sakko einzeln'),
('8', 'trousers', 750.00, 'High-End+ - Hose einzeln'),
('8', 'vest', 525.00, 'High-End+ - Weste einzeln'),
('8', 'coat', 2850.00, 'High-End+ - Mantel'),
('8', 'tuxedo', 2850.00, 'High-End+ - Smoking'),

-- Preiskategorie 9: Luxury / Top Tier
('9', 'suit', 2400.00, 'Luxury - 2-Teiler Anzug (Top Tier)'),
('9', 'three_piece', 2700.00, 'Luxury - 3-Teiler Anzug (Top Tier)'),
('9', 'jacket', 1550.00, 'Luxury - Sakko einzeln (Top Tier)'),
('9', 'trousers', 800.00, 'Luxury - Hose einzeln (Top Tier)'),
('9', 'vest', 550.00, 'Luxury - Weste einzeln (Top Tier)'),
('9', 'coat', 3000.00, 'Luxury - Mantel (Top Tier)'),
('9', 'tuxedo', 3000.00, 'Luxury - Smoking (Top Tier)');

-- ======================================================================
-- 4. INITIAL DATA - PRICING EXTRAS
-- ======================================================================

INSERT INTO pricing_extras (extra_type, extra_price, description, is_percentage) VALUES
('monogram', 50.00, 'Monogramm-Stickerei', false),
('express', 200.00, 'Express-Lieferung (< 3 Wochen)', false),
('rush', 400.00, 'Rush Order (< 2 Wochen)', false),
('working_buttonholes', 75.00, 'Funktionierende Ärmelnähte (Kissing Buttons)', false),
('hand_stitching', 150.00, 'Handgenähte Details', false),
('silk_lining', 100.00, 'Seidenfutter statt Standard', false),
('custom_lining', 125.00, 'Individuelles Futter-Design', false),
('extra_trousers', 600.00, 'Zusätzliche Hose zum Anzug', false),
('alterations', 50.00, 'Standardanpassungen nach Anprobe', false);

-- ======================================================================
-- 5. HELPER VIEWS
-- ======================================================================

-- View: Alle aktuell gültigen Preise
CREATE OR REPLACE VIEW current_pricing AS
SELECT
    price_category,
    garment_type,
    base_price,
    description
FROM pricing_rules
WHERE
    valid_from <= NOW()
    AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY
    CAST(price_category AS INTEGER),
    garment_type;

-- View: Preise mit Fabric-Daten
CREATE OR REPLACE VIEW fabric_pricing AS
SELECT
    f.fabric_code,
    f.name AS fabric_name,
    f.supplier,
    f.additional_metadata->>'preiskat' AS price_category,
    pr.garment_type,
    pr.base_price,
    pr.description AS price_description
FROM fabrics f
CROSS JOIN pricing_rules pr
WHERE
    (f.additional_metadata->>'preiskat') = pr.price_category
    AND pr.valid_from <= NOW()
    AND (pr.valid_until IS NULL OR pr.valid_until > NOW())
ORDER BY
    f.fabric_code,
    pr.garment_type;

-- ======================================================================
-- 6. QUERY EXAMPLES
-- ======================================================================

-- Beispiel 1: Preis für einen Anzug mit Stoff fabric_code='11V1004'
/*
SELECT
    f.fabric_code,
    f.name,
    pr.garment_type,
    pr.base_price
FROM fabrics f
JOIN pricing_rules pr ON (f.additional_metadata->>'preiskat') = pr.price_category
WHERE
    f.fabric_code = '11V1004'
    AND pr.garment_type = 'suit'
    AND pr.valid_from <= NOW()
    AND (pr.valid_until IS NULL OR pr.valid_until > NOW());
*/

-- Beispiel 2: Alle verfügbaren Aufschläge
/*
SELECT
    extra_type,
    extra_price,
    description
FROM pricing_extras
ORDER BY extra_price DESC;
*/

-- Beispiel 3: Preisrange für Anzüge über alle Kategorien
/*
SELECT
    price_category,
    base_price,
    description
FROM pricing_rules
WHERE
    garment_type = 'suit'
    AND valid_from <= NOW()
    AND (valid_until IS NULL OR valid_until > NOW())
ORDER BY CAST(price_category AS INTEGER);
*/

-- ======================================================================
-- DONE ✅
-- ======================================================================
-- Nächster Schritt: Pricing Tool in workflow/nodes.py anpassen
-- um diese Tabellen zu nutzen statt Fallback-Preise
-- ======================================================================
