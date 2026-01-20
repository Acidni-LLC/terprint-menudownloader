-- Terprint Genetics Data Import
-- Generated: 2026-01-20 03:14:53
-- Total Strains: 42

-- Create temp table for import
IF OBJECT_ID('tempdb..#GeneticsImport') IS NOT NULL DROP TABLE #GeneticsImport;
CREATE TABLE #GeneticsImport (
    StrainName NVARCHAR(100),
    Parent1 NVARCHAR(100),
    Parent2 NVARCHAR(100),
    Dispensary NVARCHAR(50),
    StrainType NVARCHAR(50)
);

-- Insert genetics data
INSERT INTO #GeneticsImport (StrainName, Parent1, Parent2, Dispensary, StrainType)
VALUES
    (N'Apple MAC', N'MAC 1', N'Trophy Wife', 'muv', NULL),
    (N'Applescotti', N'Apples & Bananas', N'Biscotti', 'muv', NULL),
    (N'Berry Tart', N'Triangle Kush', N'Animal Mints', 'muv', NULL),
    (N'Black Amber', N'GMO', N'OZ Kush Bx2', 'muv', NULL),
    (N'Blue Raz', N'Yadada', N'E85', 'cookies', 'hybrid'),
    (N'Cinnamon Milk', N'Cereal A La Mode', N'Sherbz', 'cookies', 'indica hybrid'),
    (N'Cromagnon Man', N'Triple Mints', N'Facemints', 'muv', NULL),
    (N'GG #4', N'Chocolate Diesel', N'Chemdawg 91 X Sour Diesel', 'muv', NULL),
    (N'GMO Jungle Cake', N'GMO', N'Jungle Cake', 'muv', NULL),
    (N'GMO S1', N'Chemdawg', N'GSC', 'muv', NULL),
    (N'Gary Payton', N'Snowman', N'Y Life', 'cookies', 'hybrid'),
    (N'Gelanoidz #4', N'Gelanade', N'Zkz', 'muv', NULL),
    (N'Gelanoidz #9', N'Gelanade', N'Zks', 'muv', NULL),
    (N'Gelato', N'Sunset Sherbet', N'Thin Mint Cookies', 'muv', NULL),
    (N'Ghost Vapor OG', N'Ghost OG', N'Purple Vapor', 'muv', NULL),
    (N'Glitter Bomb', N'Grape Gas #10', N'OGKB Blueberry Headband', 'muv', NULL),
    (N'Grape Mint Gas', N'The Menthol', N'Grape Gasoline', 'muv', NULL),
    (N'Hollywood', N'Lemon Cherry Gelato', N'Runtz', 'cookies', 'hybrid'),
    (N'Jokerz Candy', N'Gummiez', N'Grape Gas', 'muv', NULL),
    (N'Light Blue', N'T1', N'Kush E1', 'cookies', 'sativa'),
    (N'London Pound Cake #75', N'Sunset Sherbert', N'Nip OG', 'cookies', 'indica hybrid'),
    (N'Moonwalkers', N'Black Cherry Gelato', N'Medellin', 'cookies', 'indica hybrid'),
    (N'Nukenz', N'Shishkaberry', N'Godbud', 'cookies', 'hybrid'),
    (N'Original GSC', N'F1 DURB', N'Flo Rida OG Kush', 'cookies', 'hybrid'),
    (N'Pineapple Upside Down Cake', N'Pineapple Trainwreck', N'Cookie Monster', 'muv', NULL),
    (N'Pink Certz', N'The Menthol', N'Grape Gasoline', 'muv', NULL),
    (N'Pomegranate Shake', N'Cereal A la Mode', N'Sherb', 'cookies', 'hybrid'),
    (N'Purple Punch', N'Larry OG', N'Granddaddy Purple', 'muv', NULL),
    (N'Red Velvet', N'Lemon Cherry Gelato', N'Pina Acai', 'cookies', 'indica hybrid'),
    (N'Rocky Road', N'Root Beer Float', N'Birthday Cake', 'muv', NULL),
    (N'Sherbert Haze', N'Sherbert B', N'1 X Neville''s Haze', 'muv', NULL),
    (N'Super Lemon G', N'G13', N'Colombian Gold B', 'muv', NULL),
    (N'Tahitian Lime', N'TangEray', N'Sirius Chem D', 'cookies', 'sativa hybrid'),
    (N'The Soap', N'Animal Mints', N'Kush Mints', 'muv', NULL),
    (N'Triangle Kush', N'Hindu Kush', N'Lemon Thai x Chemdawg', 'muv', NULL),
    (N'Triple Scoop', N'Lemon Cherry Gelato', N'Honey Bun', 'cookies', 'hybrid'),
    (N'Tropical Teeth #2', N'Ice Cream Cake', N'Grape Teeth', 'muv', NULL),
    (N'Tropical Teeth #8', N'Ice Cream Cake', N'Grape Teeth', 'muv', NULL),
    (N'Wino #4', N'Cherry Punch', N'Grape Teeth', 'muv', NULL),
    (N'Wino #9', N'Cherry Punch', N'Grape Teeth', 'muv', NULL),
    (N'Yuzu Sour', N'Orange Sherbert 52', N'Oz Kush F2 #15 x Gastro Pop', 'muv', NULL),
    (N'Zero Gravity', N'GMO', N'Oreoz', 'cookies', 'indica');


-- Merge into production tables (example)
-- MERGE INTO StrainGenetics AS target
-- USING #GeneticsImport AS source
-- ON target.StrainName = source.StrainName
-- WHEN MATCHED THEN UPDATE SET ...
-- WHEN NOT MATCHED THEN INSERT ...

SELECT * FROM #GeneticsImport ORDER BY StrainName;
