-- MySQL dump 10.13  Distrib 8.4.11, for Linux (x86_64)
--
-- Host: localhost    Database: cqc_mo103_qa
-- ------------------------------------------------------
-- Server version	8.4.11

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('20260929_02');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bin_mappings`
--

DROP TABLE IF EXISTS `bin_mappings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bin_mappings` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `crop_type` varchar(32) DEFAULT NULL,
  `cultivar` varchar(32) DEFAULT NULL,
  `quality_grade` varchar(32) DEFAULT NULL,
  `bin_code` varchar(64) NOT NULL,
  `is_reinspection` tinyint(1) NOT NULL DEFAULT '0',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(3) NOT NULL,
  `updated_at` datetime(3) NOT NULL,
  `sweetness_band` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bin_mappings_bin_code` (`bin_code`),
  UNIQUE KEY `uq_bin_mappings_normal_combination` (`crop_type`,`cultivar`,`quality_grade`,`sweetness_band`),
  KEY `ix_bin_mappings_active_reinspection` (`is_active`,`is_reinspection`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bin_mappings`
--

LOCK TABLES `bin_mappings` WRITE;
/*!40000 ALTER TABLE `bin_mappings` DISABLE KEYS */;
INSERT INTO `bin_mappings` VALUES (1,'apple','fuji','L','DEMO_BIN_01',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(2,'apple','fuji','L','DEMO_BIN_02',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(3,'apple','fuji','M','DEMO_BIN_03',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(4,'apple','fuji','M','DEMO_BIN_04',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(5,'apple','fuji','S','DEMO_BIN_05',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(6,'apple','fuji','S','DEMO_BIN_06',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(7,'apple','yanggwang','L','DEMO_BIN_07',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(8,'apple','yanggwang','L','DEMO_BIN_08',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(9,'apple','yanggwang','M','DEMO_BIN_09',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(10,'apple','yanggwang','M','DEMO_BIN_10',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(11,'apple','yanggwang','S','DEMO_BIN_11',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','less_sweet'),(12,'apple','yanggwang','S','DEMO_BIN_12',0,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000','sweet'),(13,NULL,NULL,NULL,'TEST_REINSPECTION_BIN',1,1,'2026-09-29 00:00:00.000','2026-09-29 00:00:00.000',NULL);
/*!40000 ALTER TABLE `bin_mappings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `control_attempts`
--

DROP TABLE IF EXISTS `control_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `control_attempts` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `command_id` varchar(64) NOT NULL,
  `inspection_id` varchar(64) NOT NULL,
  `attempt_no` int NOT NULL,
  `requested_bin_code` varchar(64) NOT NULL,
  `command_type` varchar(32) NOT NULL,
  `control_status` varchar(32) NOT NULL,
  `requested_at` datetime(3) NOT NULL,
  `responded_at` datetime(3) DEFAULT NULL,
  `response_time_ms` decimal(10,3) DEFAULT NULL,
  `failure_reason` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_control_attempts_command_id` (`command_id`),
  UNIQUE KEY `uq_control_attempts_inspection_attempt` (`inspection_id`,`attempt_no`),
  KEY `ix_control_attempts_inspection_requested_at` (`inspection_id`,`requested_at`),
  KEY `ix_control_attempts_status_requested_at` (`control_status`,`requested_at`),
  CONSTRAINT `fk_control_attempts_inspection_id_inspections` FOREIGN KEY (`inspection_id`) REFERENCES `inspections` (`inspection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `control_attempts`
--

LOCK TABLES `control_attempts` WRITE;
/*!40000 ALTER TABLE `control_attempts` DISABLE KEYS */;
/*!40000 ALTER TABLE `control_attempts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inspection_errors`
--

DROP TABLE IF EXISTS `inspection_errors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_errors` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `inspection_id` varchar(64) NOT NULL,
  `component` varchar(32) NOT NULL,
  `error_code` varchar(64) NOT NULL,
  `message` text,
  `diagnostic_data` json DEFAULT NULL,
  `occurred_at` datetime(3) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_inspection_errors_code_occurred_at` (`error_code`,`occurred_at`),
  KEY `ix_inspection_errors_component_occurred_at` (`component`,`occurred_at`),
  KEY `ix_inspection_errors_inspection_occurred_at` (`inspection_id`,`occurred_at`),
  CONSTRAINT `fk_inspection_errors_inspection_id_inspections` FOREIGN KEY (`inspection_id`) REFERENCES `inspections` (`inspection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inspection_errors`
--

LOCK TABLES `inspection_errors` WRITE;
/*!40000 ALTER TABLE `inspection_errors` DISABLE KEYS */;
/*!40000 ALTER TABLE `inspection_errors` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inspections`
--

DROP TABLE IF EXISTS `inspections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspections` (
  `inspection_id` varchar(64) NOT NULL,
  `source_reference` varchar(255) DEFAULT NULL,
  `created_at` datetime(3) NOT NULL,
  `completed_at` datetime(3) DEFAULT NULL,
  `updated_at` datetime(3) NOT NULL,
  `crop_type` varchar(32) NOT NULL,
  `predicted_cultivar` varchar(32) DEFAULT NULL,
  `predicted_grade` varchar(32) DEFAULT NULL,
  `cultivar_confidence` decimal(7,6) DEFAULT NULL,
  `quality_confidence` decimal(7,6) DEFAULT NULL,
  `applied_cultivar_threshold` decimal(7,6) NOT NULL,
  `applied_quality_threshold` decimal(7,6) NOT NULL,
  `model_name` varchar(128) DEFAULT NULL,
  `model_version` varchar(128) DEFAULT NULL,
  `preprocessing_version` varchar(128) DEFAULT NULL,
  `used_frame_count` int DEFAULT NULL,
  `inference_time_ms` decimal(10,3) DEFAULT NULL,
  `review_required` tinyint(1) NOT NULL DEFAULT '0',
  `target_bin_code` varchar(64) DEFAULT NULL,
  `inspection_status` varchar(32) NOT NULL,
  `control_status` varchar(32) NOT NULL,
  `persistence_status` varchar(32) NOT NULL,
  `error_code` varchar(64) DEFAULT NULL,
  `deadline_exceeded` tinyint(1) NOT NULL DEFAULT '0',
  `exclude_from_normal_stats` tinyint(1) NOT NULL DEFAULT '0',
  `is_reviewed` tinyint(1) NOT NULL DEFAULT '0',
  `suspected_error_type` varchar(32) DEFAULT NULL,
  `review_note` varchar(500) DEFAULT NULL,
  `reviewed_at` datetime(3) DEFAULT NULL,
  `late_result_received_at` datetime(3) DEFAULT NULL,
  `late_result_payload` json DEFAULT NULL,
  `virtual_brix` decimal(4,1) DEFAULT NULL,
  `brix_source` varchar(64) DEFAULT NULL,
  `brix_is_measured` tinyint(1) NOT NULL DEFAULT '0',
  `sweetness_band` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`inspection_id`),
  KEY `ix_inspections_control_status_created_at` (`control_status`,`created_at`),
  KEY `ix_inspections_created_at_id` (`created_at`,`inspection_id`),
  KEY `ix_inspections_cultivar_grade_created_at` (`predicted_cultivar`,`predicted_grade`,`created_at`),
  KEY `ix_inspections_error_created_at` (`error_code`,`created_at`),
  KEY `ix_inspections_model_version_created_at` (`model_version`,`created_at`),
  KEY `ix_inspections_review_created_at` (`is_reviewed`,`suspected_error_type`,`created_at`),
  KEY `ix_inspections_status_created_at` (`inspection_status`,`created_at`),
  KEY `ix_inspections_target_bin_created_at` (`target_bin_code`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inspections`
--

LOCK TABLES `inspections` WRITE;
/*!40000 ALTER TABLE `inspections` DISABLE KEYS */;
/*!40000 ALTER TABLE `inspections` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-13  3:30:38
