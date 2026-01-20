-- Genetics Import - 45 strains
-- Generated: 2026-01-20T04:54:48.052465
-- Sources: Menu JSON + Menu Descriptions (MÜV, Cookies)

-- Check if table exists (create if needed)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Genetics')
BEGIN
    CREATE TABLE Genetics (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        StrainName NVARCHAR(255) NOT NULL,
        Parent1 NVARCHAR(255),
        Parent2 NVARCHAR(255),
        Dispensary NVARCHAR(100),
        Source NVARCHAR(100),
        Confidence NVARCHAR(50),
        CreatedDate DATETIME DEFAULT GETDATE(),
        CONSTRAINT UQ_StrainName UNIQUE(StrainName)
    )
END
GO

-- Insert genetics (with duplicate handling)
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Apples & Bananas', 'Platinum Cookies', 'Granddaddy Purple', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Apples & Bananas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Applescotti', 'Apples', 'Bananas And Biscotti Strikes The Perfect Balance Between Deep Relaxation And A Euphoric', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Applescotti');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Berry Tart', 'Triangle Kush', 'Animal Mints

Effects', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Berry Tart');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Black Amber', 'Gmo', 'Oz Kush Bx', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Black Amber');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Blue Raz', 'E85', 'Doggy Bagg', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Blue Raz');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Cookies Select - Apples & Bananas', 'Platinum Cookies', 'Granddaddy Purple', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Cookies Select - Apples & Bananas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Cromagnon Man', 'Triple Mints', 'Facemints', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Cromagnon Man');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Dosilato', 'Dos', 'Gelato', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Dosilato');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'E85', 'Wedding Cake', 'Project 4516', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'E85');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Emergen C', 'Orange Push Pop', 'Sunset Sherbet', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Emergen C');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Emergen C (B)', 'Orange Push Pop', 'Sunset Sherbet', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Emergen C (B)');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'GMO Jungle Cake', 'Gmo', 'Jungle Cake', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'GMO Jungle Cake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'GMO S1', 'Chemdawg 91', 'Gsc', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'GMO S1');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelato', 'Sunset Sherbet', 'Thin Mint Cookies', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelato');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelato X', 'Gelato', 'By Greendawg Has', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelato X');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Georgia Pie x Gastro Pop', 'Georgia Pie', 'Gastro Pop', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Georgia Pie x Gastro Pop');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Ghost Vapor OG', 'Ghost Og', 'Purple Vapor', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Ghost Vapor OG');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Glitter Bomb', 'Grape Gas 10', 'Ogkb Blueberry Headband', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Glitter Bomb');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Gasoline', 'Grape Pie', 'Jet Fuel Gelato', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Gasoline');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Junky', 'Animal Mints', 'Grape Gas', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Junky');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Mint Gas', 'The Menthol', 'Grape Gasoline', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Mint Gas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Guava Casquitos', 'Animal Cookies', 'Guavaz', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Guava Casquitos');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gush Mints', 'Kush Mints With (F1 Durb', 'Gushers)', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gush Mints');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Hollywood', 'By Crossing Lemon Cherry Gelato', 'Runtz', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Hollywood');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Hylife Trix', 'Hylyfe', 'Gorilla Breath', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Hylife Trix');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Ice Cream Candy', 'Dolato', 'Slurricane 23 Is Both Calming And Stimulating', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Ice Cream Candy');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Jokerz Candy', 'Gummiez', 'Grape Gas Delivers A Perfectly Balanced High', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Jokerz Candy');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Mint Diesel', 'The Menthol', 'Grape Diesel Provides A Buzzy Yet Calming Boost', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Mint Diesel');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Mint Shake', 'Wedding Cake', 'Kush Mints', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Mint Shake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Minty Blizzard', 'Amnesia Haze', 'The Mentho', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Minty Blizzard');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Moonwalkers', 'Black Cherry Gelato', 'Medellin With A Unique Terp Profile And High Potency', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Moonwalkers');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Nukenz - Manager''s Special', 'Shishkaberry', 'Godbud', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Nukenz - Manager''s Special');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Pineapple Upside Down Cake', 'Pineapple Trainwreck', 'Cookie Monster', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Pineapple Upside Down Cake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Pink Certz', 'The Menthol', 'Grape Gasoline', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Pink Certz');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Purple Milk', 'Horchata', 'Grape Gasoline', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Purple Milk');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Red Velvet', 'The Ever-Popular Lemon Cherry Gelato', 'The In-House-Made Cross Pina Acai', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Red Velvet');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Rocky Road', 'Root Beer Float', 'Birthday Cake', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Rocky Road');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Sherbert Haze', 'Sherbert Bx1', 'Neville''S Haze Blends Creamy Sherbet-Like Flavors With A Zesty Haze Kick', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Sherbert Haze');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Space Lime Continuum', 'Tahiti Lime', 'Oreoz', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Space Lime Continuum');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Space Lime Continuum - Manager''s Special', 'Tahiti Lime', 'Oreoz', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Space Lime Continuum - Manager''s Special');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'The Soap', 'Animal Mints', 'Kush Mints That Will Leave You Feeling Squeaky Clean', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'The Soap');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Triangle Kush', 'Hindu Kush', 'Lemon Thai', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Triangle Kush');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Tropical Teeth #2', 'Ice Cream Cake', 'Grape Teeth', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Tropical Teeth #2');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Tropical Teeth #8', 'Ice Cream Cake', 'Grape Teeth', 'muv', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Tropical Teeth #8');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Zero Gravity', 'Gmo', 'Oreoz', 'cookies', 'Menu Description Parsing', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Zero Gravity');

-- Verification query
SELECT COUNT(*) AS TotalGenetics FROM Genetics;
SELECT Source, COUNT(*) AS Count FROM Genetics GROUP BY Source;