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
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `control_attempts`
--

LOCK TABLES `control_attempts` WRITE;
/*!40000 ALTER TABLE `control_attempts` DISABLE KEYS */;
INSERT INTO `control_attempts` VALUES (1,'880728ed-1df7-4bb8-9522-72eaaeafefd8','6f523d16-6ba2-4c44-bc2c-7f7aa68e619c',1,'DEMO_BIN_12','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:41:07.816','2026-10-14 00:41:07.816',0.051,NULL),(2,'66a745b1-e769-4629-875e-b42d7dbf21b3','c1f89606-a2ac-4ad0-b41a-04cf724f056e',1,'DEMO_BIN_05','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:41:09.834','2026-10-14 00:41:09.834',0.050,NULL),(3,'9475211d-3944-441a-bcc8-6c9ea4b3a6af','f15a0697-82bc-45e3-a3cb-0d7b0a9c48ac',1,'DEMO_BIN_12','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:41:12.085','2026-10-14 00:41:12.086',0.057,NULL),(4,'6e2a0cea-9185-4abc-b0e9-154bd5434a7b','9f0a8822-c79f-48b7-8b87-30492b9f7566',1,'DEMO_BIN_06','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:41:16.773','2026-10-14 00:41:16.773',0.072,NULL),(5,'f8cbeac5-7b1e-45fa-b5f5-0b8315f9fb4b','2053493c-b0b3-44cf-9d21-190ccc9bf238',1,'DEMO_BIN_02','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:23.599','2026-10-14 00:42:23.599',0.051,NULL),(6,'8474a8ce-d725-4579-b258-ea5b2b0949a1','6c262d50-ff21-419c-80cf-9817d3e78f15',1,'DEMO_BIN_10','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:26.164','2026-10-14 00:42:26.164',0.054,NULL),(7,'32471c1b-c041-467e-8c06-02c0ff79c1e4','9e0a3bd0-3d52-403e-8ce8-828ae210c33a',1,'DEMO_BIN_02','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:28.080','2026-10-14 00:42:28.081',0.050,NULL),(8,'c95451f7-d009-47aa-8124-01fc42f5e1bd','42a09429-f436-4709-9b53-0cfacd5d0fa1',1,'DEMO_BIN_11','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:31.136','2026-10-14 00:42:31.136',0.068,NULL),(9,'a1db411b-5970-4243-8292-693132185e2b','4aa3a081-58d7-484a-9866-5ff6b287ee21',1,'DEMO_BIN_12','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:33.669','2026-10-14 00:42:33.669',0.061,NULL),(10,'ad9bd8d5-3a7d-44d6-aabd-32f385e3c256','c178e20b-d7f5-4245-a704-afa771120e45',1,'DEMO_BIN_10','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:36.659','2026-10-14 00:42:36.659',0.055,NULL),(11,'7cb7eda8-21ba-4ee5-97f1-e8e9731a2125','c519ac16-c877-4e60-8efd-e75755ed6119',1,'DEMO_BIN_04','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:39.168','2026-10-14 00:42:39.168',0.058,NULL),(12,'9de278c1-bedf-45d0-a1c2-8b351868c17e','e6de6c34-43e1-412f-a204-ed9556192dd9',1,'DEMO_BIN_04','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:48.127','2026-10-14 00:42:48.127',0.077,NULL),(13,'0f3332cb-3b08-4b16-9f9c-123cbf83c8c2','d9d8fa8e-719b-4c30-84be-738a0a923f19',1,'DEMO_BIN_08','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:51.071','2026-10-14 00:42:51.071',0.048,NULL),(14,'40a18aec-55e1-4fba-83f1-ff58bf28ac4d','360b8b6a-1a55-47ce-89c6-661bc1eb46fa',1,'DEMO_BIN_06','ROUTE_TO_BIN','SUCCEEDED','2026-10-14 00:42:56.206','2026-10-14 00:42:56.206',0.046,NULL);
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
INSERT INTO `inspections` VALUES ('2053493c-b0b3-44cf-9d21-190ccc9bf238','demo-601031005000-001','2026-10-14 00:42:22.586','2026-10-14 00:42:23.599','2026-10-14 00:42:23.599','apple','fuji','L',1.000000,0.869923,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,177.271,0,'DEMO_BIN_02','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',16.8,NULL,0,'sweet'),('360b8b6a-1a55-47ce-89c6-661bc1eb46fa','demo-601033017000-006','2026-10-14 00:42:55.316','2026-10-14 00:42:56.206','2026-10-14 00:42:56.206','apple','fuji','S',0.999999,0.999907,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,194.164,0,'DEMO_BIN_06','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.0,NULL,0,'sweet'),('42a09429-f436-4709-9b53-0cfacd5d0fa1','demo-601143005000-001','2026-10-14 00:42:30.149','2026-10-14 00:42:31.137','2026-10-14 00:42:31.137','apple','yanggwang','S',0.990772,0.845023,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,271.686,0,'DEMO_BIN_11','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',12.3,NULL,0,'less_sweet'),('4aa3a081-58d7-484a-9866-5ff6b287ee21','demo-601143010000-002','2026-10-14 00:42:32.585','2026-10-14 00:42:33.669','2026-10-14 00:42:33.669','apple','yanggwang','S',0.669163,0.999184,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,205.849,0,'DEMO_BIN_12','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.7,NULL,0,'sweet'),('6c262d50-ff21-419c-80cf-9817d3e78f15','demo-601142012000-002','2026-10-14 00:42:25.277','2026-10-14 00:42:26.164','2026-10-14 00:42:26.164','apple','yanggwang','M',0.999735,0.938182,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,196.870,0,'DEMO_BIN_10','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.8,NULL,0,'sweet'),('6f523d16-6ba2-4c44-bc2c-7f7aa68e619c','demo-601143002000-006','2026-10-14 00:41:06.601','2026-10-14 00:41:07.816','2026-10-14 00:41:07.816','apple','yanggwang','S',0.999996,0.999904,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,194.543,0,'DEMO_BIN_12','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.6,NULL,0,'sweet'),('9e0a3bd0-3d52-403e-8ce8-828ae210c33a','demo-601031011000-005','2026-10-14 00:42:27.212','2026-10-14 00:42:28.081','2026-10-14 00:42:28.081','apple','fuji','L',0.999998,0.869836,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,225.366,0,'DEMO_BIN_02','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',16.8,NULL,0,'sweet'),('9f0a8822-c79f-48b7-8b87-30492b9f7566','demo-601033001000-003','2026-10-14 00:41:15.517','2026-10-14 00:41:16.773','2026-10-14 00:41:16.773','apple','fuji','S',1.000000,0.981959,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,265.284,0,'DEMO_BIN_06','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.9,NULL,0,'sweet'),('c178e20b-d7f5-4245-a704-afa771120e45','demo-601142004000-001','2026-10-14 00:42:35.748','2026-10-14 00:42:36.659','2026-10-14 00:42:36.659','apple','yanggwang','M',0.999820,0.814662,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,232.204,0,'DEMO_BIN_10','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.0,NULL,0,'sweet'),('c1f89606-a2ac-4ad0-b41a-04cf724f056e','demo-601033019000-001','2026-10-14 00:41:09.082','2026-10-14 00:41:09.834','2026-10-14 00:41:09.834','apple','fuji','S',1.000000,0.999139,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,171.522,0,'DEMO_BIN_05','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',12.9,NULL,0,'less_sweet'),('c519ac16-c877-4e60-8efd-e75755ed6119','demo-601032026000-000','2026-10-14 00:42:38.011','2026-10-14 00:42:39.168','2026-10-14 00:42:39.168','apple','fuji','M',1.000000,0.670062,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,203.659,0,'DEMO_BIN_04','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',16.4,NULL,0,'sweet'),('d9d8fa8e-719b-4c30-84be-738a0a923f19','demo-601141006000-001','2026-10-14 00:42:50.164','2026-10-14 00:42:51.071','2026-10-14 00:42:51.071','apple','yanggwang','L',0.999930,0.895742,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,198.677,0,'DEMO_BIN_08','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.9,NULL,0,'sweet'),('e6de6c34-43e1-412f-a204-ed9556192dd9','demo-601033018000-003','2026-10-14 00:42:47.033','2026-10-14 00:42:48.127','2026-10-14 00:42:48.127','apple','fuji','M',0.999982,0.645673,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,282.616,0,'DEMO_BIN_04','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',15.5,NULL,0,'sweet'),('f15a0697-82bc-45e3-a3cb-0d7b0a9c48ac','demo-601143009000-003','2026-10-14 00:41:11.178','2026-10-14 00:41:12.086','2026-10-14 00:41:12.086','apple','yanggwang','S',0.999874,0.996646,0.500000,0.600000,'mobilenet_v3_small_multiview','cqc-apple-separate12-focal-v2-cal-20260930','rgb-resize-imagenet-v1',12,231.226,0,'DEMO_BIN_12','COMPLETED','SUCCEEDED','SUCCEEDED',NULL,0,0,0,NULL,NULL,NULL,NULL,'null',14.5,NULL,0,'sweet');
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

-- Dump completed on 2026-10-14  0:43:05
