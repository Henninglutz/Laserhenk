-- Check Fabric Data Completeness
-- Run this to see how many fabrics are missing data

-- 1. Total count
SELECT
    COUNT(*) as total_fabrics,
    COUNT(name) as has_name,
    COUNT(composition) as has_composition,
    COUNT(color) as has_color,
    COUNT(pattern) as has_pattern,
    COUNT(weight) as has_weight
FROM fabrics;

-- 2. Check embeddings linkage
SELECT
    COUNT(DISTINCT fe.fabric_id) as fabrics_with_embeddings,
    COUNT(DISTINCT f.id) as total_fabrics,
    COUNT(DISTINCT f.id) - COUNT(DISTINCT fe.fabric_id) as fabrics_without_embeddings
FROM fabrics f
LEFT JOIN fabric_embeddings fe ON f.id = fe.fabric_id;

-- 3. Sample of incomplete fabrics
SELECT
    id,
    fabric_code,
    name,
    composition,
    color,
    pattern,
    weight,
    CASE
        WHEN name IS NULL AND composition IS NULL AND color IS NULL THEN 'CRITICAL: All fields NULL'
        WHEN name IS NULL THEN 'Missing name'
        WHEN composition IS NULL THEN 'Missing composition'
        ELSE 'Partial data'
    END as status
FROM fabrics
WHERE name IS NULL
   OR composition IS NULL
   OR color IS NULL
LIMIT 20;

-- 4. Check if embeddings have content
SELECT
    fe.fabric_id,
    f.fabric_code,
    f.name,
    LEFT(fe.content, 100) as embedding_content_preview,
    pg_column_size(fe.embedding) as embedding_size_bytes
FROM fabric_embeddings fe
JOIN fabrics f ON fe.fabric_id = f.id
LIMIT 10;
