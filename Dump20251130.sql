CREATE DATABASE  IF NOT EXISTS `stellar` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `stellar`;
-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: stellar
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `assets`
--

DROP TABLE IF EXISTS `assets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `assets` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `project_id` int NOT NULL,
  `vintage_year` int NOT NULL,
  `asset_code` varchar(255) NOT NULL,
  `asset_issuer_address` varchar(255) NOT NULL,
  `contract_id` varchar(255) DEFAULT NULL,
  `is_frozen` tinyint(1) DEFAULT '0',
  `total_supply` decimal(20,7) NOT NULL,
  `origin_request_id` bigint DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `price_per_ton` decimal(20,7) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `project_id` (`project_id`),
  KEY `origin_request_id` (`origin_request_id`),
  CONSTRAINT `assets_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`),
  CONSTRAINT `assets_ibfk_2` FOREIGN KEY (`origin_request_id`) REFERENCES `tokenization_requests` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `assets`
--

LOCK TABLES `assets` WRITE;
/*!40000 ALTER TABLE `assets` DISABLE KEYS */;
INSERT INTO `assets` VALUES (9,2,2025,'RCYCL_1_2025','GAF62I3FQGSCOBUGUPFIFYX6NF5GXJ3AYXFU6S47JG3ZG5Z7UJG4QDJO','CC3EVL33OZ3HX4ZMU2SLEYHJZAXO4HOE4XP2QZDSKLEXT5I3PRSTMN2N',0,500000.0000000,5,'2025-11-30 05:00:19',0.0100000);
/*!40000 ALTER TABLE `assets` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `categories`
--

DROP TABLE IF EXISTS `categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `categories`
--

LOCK TABLES `categories` WRITE;
/*!40000 ALTER TABLE `categories` DISABLE KEYS */;
INSERT INTO `categories` VALUES (1,'Solar'),(2,'Wind'),(3,'Recycle'),(4,'Forestry'),(5,'Hydroelectric');
/*!40000 ALTER TABLE `categories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `projects`
--

DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `projects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registry_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `project_identifier` varchar(50) NOT NULL,
  `name` varchar(255) NOT NULL,
  `issuer_id` bigint DEFAULT NULL,
  `description` text,
  `country` varchar(100) DEFAULT NULL,
  `location_geo` point DEFAULT NULL,
  `image_url` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `project_identifier` (`project_identifier`),
  KEY `issuer_id` (`issuer_id`),
  KEY `registry_id` (`registry_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `projects_ibfk_1` FOREIGN KEY (`issuer_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `projects_ibfk_2` FOREIGN KEY (`registry_id`) REFERENCES `registries` (`id`),
  CONSTRAINT `projects_ibfk_3` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `projects`
--

LOCK TABLES `projects` WRITE;
/*!40000 ALTER TABLE `projects` DISABLE KEYS */;
INSERT INTO `projects` VALUES (1,1,2,'WND-1','Galata Wind',1,'It is a good clean wind powered electricity generation project !','Turkiye',_binary '\0\0\0\0\0\0\0˚˙V7ß=@/\◊a]∏ÄD@','/uploads/projects/1/1.jpg'),(2,1,3,'RCYCL-1','Waste Recycle',1,'Recycling plastic waste','USA',_binary '\0\0\0\0\0\0\0‡°ü¬èÛZ¿V%¥9#\¬B@','/uploads/projects/2/2.jpg');
/*!40000 ALTER TABLE `projects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `registries`
--

DROP TABLE IF EXISTS `registries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `registries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `website` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `registries`
--

LOCK TABLES `registries` WRITE;
/*!40000 ALTER TABLE `registries` DISABLE KEYS */;
INSERT INTO `registries` VALUES (1,'Verra','https://verra.org/'),(2,'Gold Standard','https://www.goldstandard.org/');
/*!40000 ALTER TABLE `registries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tokenization_requests`
--

DROP TABLE IF EXISTS `tokenization_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tokenization_requests` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `issuer_id` bigint NOT NULL,
  `project_id` int NOT NULL,
  `vintage_year` int NOT NULL,
  `quantity` decimal(20,7) NOT NULL,
  `price_per_ton` decimal(20,7) DEFAULT NULL,
  `serial_number_start` varchar(100) DEFAULT NULL,
  `serial_number_end` varchar(100) DEFAULT NULL,
  `proof_document_url` varchar(255) NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED','MINTED') DEFAULT 'PENDING',
  `admin_note` text,
  PRIMARY KEY (`id`),
  KEY `issuer_id` (`issuer_id`),
  KEY `project_id` (`project_id`),
  CONSTRAINT `tokenization_requests_ibfk_1` FOREIGN KEY (`issuer_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `tokenization_requests_ibfk_2` FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tokenization_requests`
--

LOCK TABLES `tokenization_requests` WRITE;
/*!40000 ALTER TABLE `tokenization_requests` DISABLE KEYS */;
INSERT INTO `tokenization_requests` VALUES (1,1,1,2023,100.0000000,2.0000000,'1','2','/uploads/documents/1.pdf','MINTED','\nContract: CB53R7CCX57B22XXZF3EV7TY4R23EF6CONMMAA6IJ3JBHURY6VSMATTS'),(2,1,1,2013,500.0000000,0.5000000,'009','898','/uploads/documents/2.pdf','MINTED','\nContract: CA72QY2Y5HPVED7UBFTHIK3TBNTTRHNJX2CF7OD7K4YP6PKYO6PN3XZN'),(3,1,2,2024,200.0000000,0.0100000,'1231','3414','/uploads/documents/3.pdf','MINTED','\nContract: CCYYI63J423PSBN52LLBJKGPSNJMYKSSHAUDUTNB6AA57WNKSLDKOCKA'),(4,1,2,2019,6000.0000000,0.0100000,'222','111','/uploads/documents/4.pdf','MINTED','\nContract: CC5EOFIA6V54OBCSFAGPMNEP2MSMOK3JIQWEGNQHASSWXDR7ITCVAQTE'),(5,1,2,2025,500000.0000000,0.0100000,'000','112','/uploads/documents/5.pdf','MINTED','\nContract: CC3EVL33OZ3HX4ZMU2SLEYHJZAXO4HOE4XP2QZDSKLEXT5I3PRSTMN2N');
/*!40000 ALTER TABLE `tokenization_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` bigint NOT NULL AUTO_INCREMENT,
  `wallet_address` varchar(200) NOT NULL,
  `username` varchar(200) NOT NULL,
  `email` varchar(200) DEFAULT NULL,
  `current_nonce` varchar(255) DEFAULT NULL,
  `role` enum('USER','ISSUER','ADMIN') DEFAULT 'USER',
  `company_registiration_no` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `wallet_address` (`wallet_address`),
  UNIQUE KEY `username` (`username`),
  KEY `wallet_address_2` (`wallet_address`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'GAF62I3FQGSCOBUGUPFIFYX6NF5GXJ3AYXFU6S47JG3ZG5Z7UJG4QDJO','emirhan','emirhan@gmail.com',NULL,'ISSUER',NULL),(2,'GDDCXUKLSVFSCOAPT7DOU6AC32XYDWBND37NOOXVLFV5PXTUKKDDZIEP','admin','admin@gmail.com',NULL,'ADMIN',NULL),(3,'GANZVNBVFYCUMBKV4AQ2JH7X7S6IDLLXA2E5BDB3OUIG5AU2LDMZ26SP','nisa','nisa@gmail.com',NULL,'USER',NULL),(4,'GCOEL6G3SUUCB54RRTMU5WR3IT6QZ6GZN4HLBKJUNN67OXMCOXGN7BN7','fatih','fatih@gmail.com',NULL,'USER',NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-11-30  8:54:17
