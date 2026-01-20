-- TERPRINT GENETICS IMPORT
-- Generated: 2026-01-20T04:55:39.240894
-- Total Strains: 63
-- Sources: Menu JSON Extraction + Menu Description Parsing

-- Create table if not exists
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

INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Apple MAC', 'MAC 1', 'Trophy Wife', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Apple MAC');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Apples & Bananas', 'Platinum Cookies', 'Granddaddy Purple', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Apples & Bananas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Applescotti', 'Apples & Bananas', 'Biscotti', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Applescotti');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Berry Tart', 'Triangle Kush', 'Animal Mints', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Berry Tart');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Black Amber', 'GMO', 'OZ Kush Bx2', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Black Amber');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Blue Raz', 'Yadada', 'E85', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Blue Raz');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Cinnamon Milk', 'Cereal A La Mode', 'Sherbz', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Cinnamon Milk');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Cookies Select - Apples & Bananas', 'Platinum Cookies', 'Granddaddy Purple', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Cookies Select - Apples & Bananas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Cromagnon Man', 'Triple Mints', 'Facemints', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Cromagnon Man');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Dosilato', 'Dos', 'Gelato', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Dosilato');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'E85', 'Wedding Cake', 'Project 4516', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'E85');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Emergen C', 'Orange Push Pop', 'Sunset Sherbet', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Emergen C');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Emergen C (B)', 'Orange Push Pop', 'Sunset Sherbet', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Emergen C (B)');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'GG #4', 'Chocolate Diesel', 'Chemdawg 91 X Sour Diesel', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'GG #4');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'GMO Jungle Cake', 'GMO', 'Jungle Cake', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'GMO Jungle Cake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'GMO S1', 'Chemdawg', 'GSC', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'GMO S1');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gary Payton', 'Snowman', 'Y Life', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gary Payton');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelanoidz #4', 'Gelanade', 'Zkz', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelanoidz #4');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelanoidz #9', 'Gelanade', 'Zks', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelanoidz #9');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelato', 'Sunset Sherbet', 'Thin Mint Cookies', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelato');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gelato X', 'Gelato', 'By Greendawg Has', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gelato X');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Georgia Pie x Gastro Pop', 'Georgia Pie', 'Gastro Pop', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Georgia Pie x Gastro Pop');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Ghost Vapor OG', 'Ghost OG', 'Purple Vapor', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Ghost Vapor OG');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Glitter Bomb', 'Grape Gas #10', 'OGKB Blueberry Headband', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Glitter Bomb');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Gasoline', 'Grape Pie', 'Jet Fuel Gelato', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Gasoline');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Junky', 'Animal Mints', 'Grape Gas', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Junky');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Grape Mint Gas', 'The Menthol', 'Grape Gasoline', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Grape Mint Gas');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Guava Casquitos', 'Animal Cookies', 'Guavaz', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Guava Casquitos');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Gush Mints', 'Kush Mints With (F1 Durb', 'Gushers)', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Gush Mints');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Hollywood', 'Lemon Cherry Gelato', 'Runtz', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Hollywood');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Hylife Trix', 'Hylyfe', 'Gorilla Breath', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Hylife Trix');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Ice Cream Candy', 'Dolato', 'Slurricane 23 Is Both Calming And Stimulating', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Ice Cream Candy');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Jokerz Candy', 'Gummiez', 'Grape Gas', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Jokerz Candy');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Light Blue', 'T1', 'Kush E1', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Light Blue');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'London Pound Cake #75', 'Sunset Sherbert', 'Nip OG', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'London Pound Cake #75');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Mint Diesel', 'The Menthol', 'Grape Diesel Provides A Buzzy Yet Calming Boost', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Mint Diesel');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Mint Shake', 'Wedding Cake', 'Kush Mints', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Mint Shake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Minty Blizzard', 'Amnesia Haze', 'The Mentho', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Minty Blizzard');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Moonwalkers', 'Black Cherry Gelato', 'Medellin', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Moonwalkers');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Nukenz', 'Shishkaberry', 'Godbud', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Nukenz');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Nukenz - Manager''s Special', 'Shishkaberry', 'Godbud', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Nukenz - Manager''s Special');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Original GSC', 'F1 DURB', 'Flo Rida OG Kush', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Original GSC');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Pineapple Upside Down Cake', 'Pineapple Trainwreck', 'Cookie Monster', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Pineapple Upside Down Cake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Pink Certz', 'The Menthol', 'Grape Gasoline', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Pink Certz');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Pomegranate Shake', 'Cereal A la Mode', 'Sherb', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Pomegranate Shake');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Purple Milk', 'Horchata', 'Grape Gasoline', 'muv', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Purple Milk');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Purple Punch', 'Larry OG', 'Granddaddy Purple', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Purple Punch');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Red Velvet', 'Lemon Cherry Gelato', 'Pina Acai', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Red Velvet');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Rocky Road', 'Root Beer Float', 'Birthday Cake', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Rocky Road');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Sherbert Haze', 'Sherbert B', '1 X Neville''s Haze', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Sherbert Haze');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Space Lime Continuum', 'Tahiti Lime', 'Oreoz', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Space Lime Continuum');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Space Lime Continuum - Manager''s Special', 'Tahiti Lime', 'Oreoz', 'cookies', 'Menu Description Parsing', 'High' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Space Lime Continuum - Manager''s Special');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Super Lemon G', 'G13', 'Colombian Gold B', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Super Lemon G');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Tahitian Lime', 'TangEray', 'Sirius Chem D', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Tahitian Lime');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'The Soap', 'Animal Mints', 'Kush Mints', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'The Soap');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Triangle Kush', 'Hindu Kush', 'Lemon Thai x Chemdawg', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Triangle Kush');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Triple Scoop', 'Lemon Cherry Gelato', 'Honey Bun', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Triple Scoop');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Tropical Teeth #2', 'Ice Cream Cake', 'Grape Teeth', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Tropical Teeth #2');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Tropical Teeth #8', 'Ice Cream Cake', 'Grape Teeth', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Tropical Teeth #8');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Wino #4', 'Cherry Punch', 'Grape Teeth', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Wino #4');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Wino #9', 'Cherry Punch', 'Grape Teeth', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Wino #9');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Yuzu Sour', 'Orange Sherbert 52', 'Oz Kush F2 #15 x Gastro Pop', 'muv', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Yuzu Sour');
INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) SELECT 'Zero Gravity', 'GMO', 'Oreoz', 'cookies', 'Menu JSON Extraction', 'Medium' WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = 'Zero Gravity');

-- Verification
SELECT COUNT(*) AS TotalGenetics FROM Genetics;
SELECT Source, COUNT(*) AS Count FROM Genetics GROUP BY Source ORDER BY Count DESC;
SELECT TOP 20 StrainName, Parent1, Parent2, Dispensary FROM Genetics ORDER BY StrainName;