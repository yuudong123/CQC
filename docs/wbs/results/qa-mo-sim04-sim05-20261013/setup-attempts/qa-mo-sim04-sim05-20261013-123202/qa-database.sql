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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `control_attempts`
--

LOCK TABLES `control_attempts` WRITE;
/*!40000 ALTER TABLE `control_attempts` DISABLE KEYS */;
INSERT INTO `control_attempts` VALUES (1,'f7c4ad26-9c71-4cb6-8c0f-39e98768628f','d559a54c-d303-4ba1-9280-3e7bf085eaa9',1,'DEMO_BIN_12','ROUTE_TO_BIN','SUCCEEDED','2026-10-13 03:33:07.369','2026-10-13 03:33:07.369',0.083,NULL),(2,'d4ea612a-8468-4cc6-9c9f-a5c8711bd482','50172c94-093a-4c0c-bc1b-b7bee71cc8b8',1,'DEMO_BIN_05','ROUTE_TO_BIN','SUCCEEDED','2026-10-13 03:33:09.742','2026-10-13 03:33:09.742',0.069,NULL),(3,'6a2faced-f7e3-4453-ba73-a5a2de242be0','001d06e4-c015-41a0-aae6-304d7abb1a3c',1,'DEMO_BIN_12','ROUTE_TO_BIN','SUCCEEDED','2026-10-13 03:33:11.643','2026-10-13 03:33:11.643',0.057,NULL),(4,'47d7aeee-7a83-4273-8750-211bae6c7ebf','c38ba202-862a-422f-990a-89df90652e7b',1,'DEMO_BIN_06','ROUTE_TO_BIN','SUCCEEDED','2026-10-13 03:33:13.817','2026-10-13 03:33:13.817',0.063,NULL),(5,'3d8f3d70-5110-4361-8bc0-9ec53645c08a','d553f9dd-125b-45ee-b2da-bc7e85493c06',1,'DEMO_BIN_02','ROUTE_TO_BIN','SUCCEEDED','2026-10-13 03:33:15.929','2026-10-13 03:33:15.929',0.101,NULL);
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
INSERT INTO `inspections` VALUES ('001d06e4-c015-41a0-aae6-304d7abb1a3c','demo-601143009000-003','2026-10-13 03:33:10.643','2026-10-13 03:33:11.643','2026-10-13 03:33:11.643','apple','yanggwang','S',0.999874,0.996646,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,262.919,0,'DEMO_BIN_12','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.5,NULL,0,'sweet'),('3c3d79b4-de96-4d81-a905-e1b7cf8df6fa','demo-601142012000-002','2026-10-13 03:33:19.758',NULL,'2026-10-13 03:33:19.758','apple',NULL,NULL,NULL,NULL,0.500000,0.600000,NULL,NULL,NULL,NULL,NULL,0,NULL,'PROCESSING','NOT_REQUESTED','PENDING',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.8,NULL,0,'sweet'),('50172c94-093a-4c0c-bc1b-b7bee71cc8b8','demo-601033019000-001','2026-10-13 03:33:08.606','2026-10-13 03:33:09.742','2026-10-13 03:33:09.742','apple','fuji','S',1.000000,0.999139,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,345.436,0,'DEMO_BIN_05','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',12.9,NULL,0,'less_sweet'),('c38ba202-862a-422f-990a-89df90652e7b','demo-601033001000-003','2026-10-13 03:33:12.525','2026-10-13 03:33:13.818','2026-10-13 03:33:13.818','apple','fuji','S',1.000000,0.981959,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,281.539,0,'DEMO_BIN_06','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.9,NULL,0,'sweet'),('d553f9dd-125b-45ee-b2da-bc7e85493c06','demo-601031005000-001','2026-10-13 03:33:14.628','2026-10-13 03:33:15.929','2026-10-13 03:33:15.929','apple','fuji','L',1.000000,0.869923,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,232.432,0,'DEMO_BIN_02','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',16.8,NULL,0,'sweet'),('d559a54c-d303-4ba1-9280-3e7bf085eaa9','demo-601143002000-006','2026-10-13 03:33:05.661','2026-10-13 03:33:07.369','2026-10-13 03:33:07.369','apple','yanggwang','S',0.999996,0.999904,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,554.333,0,'DEMO_BIN_12','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.6,NULL,0,'sweet');
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

-- Dump completed on 2026-10-13  3:33:21
