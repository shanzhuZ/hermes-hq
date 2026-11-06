-- MySQL dump 10.13  Distrib 8.0.32, for Win64 (x86_64)
--
-- Host: 192.168.3.124    Database: hermes-xa
-- ------------------------------------------------------
-- Server version	8.0.35

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
-- Table structure for table `collect_display_records`
--

DROP TABLE IF EXISTS `collect_display_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_display_records` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `step_key` varchar(64) NOT NULL COMMENT '步骤键，与 collect_phase_steps.step_key 一致',
  `data_type` varchar(64) NOT NULL COMMENT '数据类型：collect_profiles / collect_posts 等',
  `source_table` varchar(64) NOT NULL COMMENT '来源业务表名',
  `source_ref` varchar(128) NOT NULL COMMENT '来源主键（数字 id 或 stream_id）',
  `platform` varchar(32) DEFAULT NULL COMMENT '平台，便于 step6_post_* 过滤',
  `account_id` varchar(128) DEFAULT NULL COMMENT '平台账号 ID，关联 collect_profiles / collect_posts',
  `stream_type` varchar(16) DEFAULT NULL COMMENT '流类型 text/image，仅 identity_streams',
  `record_title` varchar(256) DEFAULT NULL COMMENT '卡片标题',
  `display_fields` json NOT NULL COMMENT '展示字段 [{label,value,type?}]',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_step_source` (`task_id`,`step_key`,`source_table`,`source_ref`),
  KEY `idx_task_type` (`task_id`,`data_type`),
  KEY `idx_task_step` (`task_id`,`step_key`),
  KEY `idx_task_platform` (`task_id`,`platform`),
  KEY `idx_task_stream` (`task_id`,`stream_type`),
  KEY `idx_task_account` (`task_id`,`account_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3385 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='前端展示用记录，与业务表双写';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_identity_streams`
--

DROP TABLE IF EXISTS `collect_identity_streams`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_identity_streams` (
  `stream_id` varchar(64) NOT NULL COMMENT '特征流唯一 ID',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `stream_type` varchar(16) NOT NULL COMMENT '流类型：text 文本流 / image 图片流',
  `source_platform` varchar(32) DEFAULT NULL COMMENT '来源平台',
  `source_account_id` varchar(128) DEFAULT NULL COMMENT '来源账号 ID',
  `source_field` varchar(64) DEFAULT NULL COMMENT '来源字段：bio 简介 / avatar 头像 / display_name 昵称 等',
  `payload_text` text COMMENT '文本流内容',
  `payload_url` varchar(512) DEFAULT NULL COMMENT '图片流 URL（头像、主页图等）',
  `validation_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '校验状态：pending 待校验 / pass 通过 / fail 失败 / low_quality 质量过低',
  `validation_detail` text COMMENT '校验说明或失败原因',
  `extra_json` json DEFAULT NULL COMMENT '扩展字段 JSON',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`stream_id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_type` (`task_id`,`stream_type`),
  KEY `idx_validation` (`task_id`,`validation_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='特征流表：从主页/简介/头像生成的文本流与图片流及校验结果';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_images`
--

DROP TABLE IF EXISTS `collect_images`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_images` (
  `image_id` varchar(64) NOT NULL COMMENT '图片记录唯一ID',
  `task_id` varchar(64) NOT NULL COMMENT '所属任务ID',
  `task_type` varchar(32) DEFAULT NULL COMMENT '任务类型，便于按业务查询',
  `source_type` varchar(32) NOT NULL COMMENT '来源：profile_avatar/profile_cover/post_media',
  `platform` varchar(32) DEFAULT NULL COMMENT '来源平台',
  `account_id` varchar(128) DEFAULT NULL COMMENT '关联账号ID',
  `post_id` varchar(128) DEFAULT NULL COMMENT '关联发文ID，对应 collect_posts.content_id',
  `profile_id` varchar(128) DEFAULT NULL COMMENT '关联主页ID，通常为 collect_profiles.account_id',
  `origin_url` text COMMENT '原始图片URL',
  `hbase_row_key` varchar(128) DEFAULT NULL COMMENT 'HBase原图RowKey',
  `content_sha256` char(64) DEFAULT NULL COMMENT '原图SHA-256，用于幂等和去重',
  `mime_type` varchar(64) DEFAULT NULL COMMENT '图片MIME类型',
  `file_size` bigint DEFAULT NULL COMMENT '原图字节数',
  `width` int DEFAULT NULL COMMENT '图片宽度',
  `height` int DEFAULT NULL COMMENT '图片高度',
  `storage_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '存储状态：pending/downloading/stored/failed',
  `analyze_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '分析状态：pending/running/completed/failed/skipped',
  `ocr_text` mediumtext COMMENT 'OCR识别文本',
  `vision_text` mediumtext COMMENT 'Vision图片描述',
  `analysis_json` json DEFAULT NULL COMMENT '结构化分析结果',
  `error_message` varchar(1000) DEFAULT NULL COMMENT '最近一次失败原因',
  `retry_count` int NOT NULL DEFAULT '0' COMMENT '处理重试次数',
  `tool_output_id` bigint DEFAULT NULL COMMENT '关联OCR/Vision工具输出ID',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  `stored_at` datetime(3) DEFAULT NULL COMMENT '原图写入HBase时间',
  `analyzed_at` datetime(3) DEFAULT NULL COMMENT '分析完成时间',
  PRIMARY KEY (`image_id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_status` (`task_id`,`analyze_status`),
  KEY `idx_task_source` (`task_id`,`source_type`),
  KEY `idx_account` (`task_id`,`platform`,`account_id`),
  KEY `idx_post` (`task_id`,`platform`,`post_id`),
  KEY `idx_sha256` (`content_sha256`),
  KEY `idx_storage_status` (`storage_status`),
  CONSTRAINT `fk_collect_images_task` FOREIGN KEY (`task_id`) REFERENCES `hermes_tasks` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='图片资产、业务关联及OCR/Vision分析结果';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_osint_hits`
--

DROP TABLE IF EXISTS `collect_osint_hits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_osint_hits` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` varchar(64) NOT NULL COMMENT '所属任务ID',
  `platform` varchar(32) DEFAULT NULL COMMENT '关联平台',
  `account_id` varchar(128) DEFAULT NULL COMMENT '关联账号ID',
  `profile_url` text COMMENT '查询用主页URL',
  `source_index` varchar(128) DEFAULT NULL COMMENT 'ES 索引名',
  `query_text` varchar(1024) DEFAULT NULL COMMENT '实际查询文本',
  `hit_count` int NOT NULL DEFAULT '0' COMMENT '命中条数',
  `hit_json` mediumtext COMMENT '命中整包JSON',
  `tool_output_id` bigint DEFAULT NULL COMMENT '关联 hermes_tool_outputs.id',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_query_index` (`task_id`,`query_text`(191),`source_index`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_account` (`task_id`,`platform`,`account_id`),
  CONSTRAINT `fk_collect_osint_hits_task` FOREIGN KEY (`task_id`) REFERENCES `hermes_tasks` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='社工库核验命中（4.3 step6_osint_es）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_phase_steps`
--

DROP TABLE IF EXISTS `collect_phase_steps`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_phase_steps` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `step_key` varchar(64) NOT NULL COMMENT '步骤键，如 step1_seed / step6_post_twitter',
  `parent_step_key` varchar(64) DEFAULT NULL COMMENT '父步骤键，如 step6_posts 的子步骤',
  `step_order` int NOT NULL COMMENT '同级排序，越小越靠前',
  `step_node` varchar(16) DEFAULT NULL COMMENT '前端链路节点，如 1 / 4 / 4.1 / 6.2',
  `title` varchar(256) NOT NULL COMMENT '前端展示标题（中文）',
  `source_tag` varchar(64) DEFAULT NULL COMMENT 'JSON列表：付费/开源/离线/自研；壳为空',
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/skipped',
  `progress_pct` tinyint DEFAULT NULL COMMENT '0-100 可选进度',
  `message` text COMMENT '步骤说明或结果摘要',
  `payload_json` json DEFAULT NULL COMMENT '前端渲染用结构化摘要',
  `started_at` datetime(3) DEFAULT NULL COMMENT '开始时间',
  `finished_at` datetime(3) DEFAULT NULL COMMENT '结束时间',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_step` (`task_id`,`step_key`),
  KEY `idx_task_order` (`task_id`,`step_order`),
  KEY `idx_task_parent` (`task_id`,`parent_step_key`),
  KEY `idx_task_status` (`task_id`,`status`)
) ENGINE=InnoDB AUTO_INCREMENT=5848 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='01采集阶段步骤表：供前端深度模式渲染';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_posts`
--

DROP TABLE IF EXISTS `collect_posts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_posts` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `platform` varchar(32) NOT NULL COMMENT '平台标识',
  `account_id` varchar(128) NOT NULL COMMENT '发文作者账号 ID',
  `content_id` varchar(128) NOT NULL COMMENT '平台内内容唯一 ID（博文ID/视频ID等）',
  `content_type` varchar(32) NOT NULL DEFAULT 'post' COMMENT '内容类型：post 原创帖 / repost 转发 / video 视频 / article 长文 / comment 评论',
  `parent_content_id` varchar(128) DEFAULT NULL COMMENT '父内容 ID，转发源帖或被评论博文',
  `title` varchar(512) DEFAULT NULL COMMENT '标题（视频、公众号等）',
  `content_text` text COMMENT '正文文本，过长时可截断',
  `content_url` varchar(512) DEFAULT NULL COMMENT '内容可访问链接',
  `published_at` datetime(3) DEFAULT NULL COMMENT '发布时间',
  `view_count` bigint DEFAULT NULL COMMENT '浏览量或播放量，无则 NULL',
  `like_count` bigint DEFAULT NULL COMMENT '点赞数',
  `comment_count` bigint DEFAULT NULL COMMENT '评论数',
  `repost_count` bigint DEFAULT NULL COMMENT '转发或分享数',
  `media_json` json DEFAULT NULL COMMENT '媒体列表 JSON：[{type, url, thumb}]',
  `metrics_json` json DEFAULT NULL COMMENT '平台扩展互动指标 JSON',
  `matched_keywords` json DEFAULT NULL COMMENT '命中关键词列表 JSON',
  `text_truncated` tinyint(1) NOT NULL DEFAULT '0' COMMENT '正文是否已截断：1 是 / 0 否',
  `tool_output_id` bigint DEFAULT NULL COMMENT '关联 hermes_tool_outputs.id',
  `raw_json` json DEFAULT NULL COMMENT '平台原始内容对象 JSON',
  `extra_json` json DEFAULT NULL COMMENT '扩展字段 JSON',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '入库时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_content` (`task_id`,`platform`,`content_id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_account` (`platform`,`account_id`),
  KEY `idx_published` (`task_id`,`published_at`)
) ENGINE=InnoDB AUTO_INCREMENT=1510 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='发文信息表：博文/视频/转发等内容明细（统一常用列 + 原始JSON）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_profiles`
--

DROP TABLE IF EXISTS `collect_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_profiles` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `platform` varchar(32) NOT NULL COMMENT '平台标识',
  `account_id` varchar(128) NOT NULL COMMENT '平台内账号 ID',
  `account_handle` varchar(256) DEFAULT NULL COMMENT '账号 @名或自定义 ID',
  `display_name` varchar(256) DEFAULT NULL COMMENT '显示昵称',
  `bio` text COMMENT '个人简介',
  `avatar_url` varchar(512) DEFAULT NULL COMMENT '头像 URL',
  `profile_url` varchar(512) DEFAULT NULL COMMENT '主页链接',
  `follower_count` bigint DEFAULT NULL COMMENT '粉丝数',
  `following_count` bigint DEFAULT NULL COMMENT '关注数',
  `content_count` bigint DEFAULT NULL COMMENT '内容总数（博文/视频等，语义因平台而异）',
  `verified` tinyint(1) DEFAULT NULL COMMENT '是否官方认证：1 是 / 0 否',
  `visibility` varchar(16) DEFAULT NULL COMMENT '可见性：public 公开 / partial 部分可见 / unknown 未知',
  `collect_status` varchar(16) DEFAULT NULL COMMENT '采集状态：success 成功 / empty 无数据 / partial 部分 / error 失败',
  `tool_output_id` bigint DEFAULT NULL COMMENT '关联 hermes_tool_outputs.id',
  `raw_json` json DEFAULT NULL COMMENT '平台原始 profile 对象 JSON，完整保留',
  `collect_options_json` json DEFAULT NULL COMMENT '本次采集条件 JSON（时间范围、条数上限等）',
  `metrics_json` json DEFAULT NULL COMMENT '平台特有指标 JSON，如 B站投币数',
  `extra_json` json DEFAULT NULL COMMENT '暂未提升为独立列的扩展字段',
  `collected_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '资料快照采集时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_account` (`task_id`,`platform`,`account_id`),
  KEY `idx_account` (`platform`,`account_id`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='人物信息表：各平台账号资料快照（统一常用列 + 原始JSON）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_step_demo_records`
--

DROP TABLE IF EXISTS `collect_step_demo_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_step_demo_records` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `step_key` varchar(64) NOT NULL COMMENT '步骤键，如 step6_osint_es',
  `record_title` varchar(256) NOT NULL COMMENT '卡片/节点标题',
  `account_id` varchar(128) DEFAULT NULL COMMENT '种子账号 ID，便于按账号过滤',
  `display_fields` json NOT NULL COMMENT '展示字段 [{label,value}]',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '同 step_key 内排序',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_step_key` (`step_key`),
  KEY `idx_step_account` (`step_key`,`account_id`),
  KEY `idx_step_sort` (`step_key`,`sort_order`,`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='写报流程演示假数据';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_task_summaries`
--

DROP TABLE IF EXISTS `collect_task_summaries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_task_summaries` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID，一对一',
  `title` varchar(256) DEFAULT NULL COMMENT '摘要标题，如「Twitter 李老师 · 跨平台采集」',
  `validated_account_count` int DEFAULT '0' COMMENT '通过校验的账号数量',
  `profile_count` int DEFAULT '0' COMMENT '采集到的人物资料条数',
  `post_count` int DEFAULT '0' COMMENT '采集到的发文条数',
  `platforms_json` json DEFAULT NULL COMMENT '涉及平台列表 JSON，如 ["twitter","bilibili"]',
  `summary_text` text COMMENT '给人阅读的简短文字摘要',
  `summary_json` json DEFAULT NULL COMMENT '结构化摘要 JSON，供报告或前端使用',
  `generated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '摘要生成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务数据摘要表：一次采集完成后的统计与摘要';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_validated_accounts`
--

DROP TABLE IF EXISTS `collect_validated_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_validated_accounts` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `platform` varchar(32) NOT NULL COMMENT '平台标识',
  `account_id` varchar(128) NOT NULL COMMENT '平台内账号 ID',
  `account_handle` varchar(256) DEFAULT NULL COMMENT '账号 @名或昵称',
  `confidence` decimal(5,4) DEFAULT NULL COMMENT '综合置信度 0～1',
  `verdict` varchar(32) NOT NULL DEFAULT 'validated' COMMENT '判定结果：validated 通过 / rejected 拒绝 / insufficient 数据不足',
  `stream_ids_json` json DEFAULT NULL COMMENT '支撑判定的特征流 ID 列表 JSON',
  `is_seed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否种子账号：1 是用户最初指定的账号 / 0 否',
  `extra_json` json DEFAULT NULL COMMENT '扩展字段 JSON',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '入库时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_account` (`task_id`,`platform`,`account_id`),
  KEY `idx_task_verdict` (`task_id`,`verdict`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='已校验账号清单：阶段7 收敛后进入分平台采集的账号列表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_video_frames`
--

DROP TABLE IF EXISTS `collect_video_frames`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_video_frames` (
  `frame_id` varchar(64) NOT NULL COMMENT '帧唯一ID',
  `video_id` varchar(64) NOT NULL COMMENT '所属视频',
  `task_id` varchar(64) NOT NULL COMMENT '所属任务',
  `platform` varchar(32) DEFAULT NULL,
  `account_id` varchar(128) DEFAULT NULL,
  `post_id` varchar(128) DEFAULT NULL,
  `frame_index` int NOT NULL COMMENT '抽帧序号，从0起',
  `timestamp_sec` decimal(10,2) NOT NULL COMMENT '视频内时间点（秒）',
  `is_preview` tinyint NOT NULL DEFAULT '0' COMMENT '是否推荐前端默认渲染：1=是（约3张）',
  `sort_order` int DEFAULT NULL COMMENT '预览排序，非预览可空',
  `local_path` varchar(512) DEFAULT NULL COMMENT '帧本地路径（上传HBase成功后可清空）',
  `hbase_row_key` varchar(128) DEFAULT NULL COMMENT 'HBase帧图RowKey，如 frm:{taskId}:{sha16}',
  `storage_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/stored/failed',
  `mime_type` varchar(64) DEFAULT 'image/jpeg',
  `file_size` bigint DEFAULT NULL,
  `width` int DEFAULT NULL,
  `height` int DEFAULT NULL,
  `content_sha256` char(64) DEFAULT NULL,
  `analyze_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/completed/failed/skipped',
  `vision_text` mediumtext COMMENT '该帧VLM描述',
  `analysis_json` json DEFAULT NULL COMMENT '该帧结构化结果',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `analyzed_at` datetime(3) DEFAULT NULL,
  PRIMARY KEY (`frame_id`),
  UNIQUE KEY `uk_video_frame_index` (`video_id`,`frame_index`),
  KEY `idx_task_video` (`task_id`,`video_id`),
  KEY `idx_video_preview` (`video_id`,`is_preview`),
  CONSTRAINT `fk_video_frames_video` FOREIGN KEY (`video_id`) REFERENCES `collect_videos` (`video_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='视频全部抽帧图及单帧分析';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collect_videos`
--

DROP TABLE IF EXISTS `collect_videos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collect_videos` (
  `video_id` varchar(64) NOT NULL COMMENT '视频记录唯一ID',
  `task_id` varchar(64) NOT NULL COMMENT '所属任务ID',
  `task_type` varchar(32) DEFAULT NULL COMMENT '任务类型',
  `source_type` varchar(32) NOT NULL DEFAULT 'post_video' COMMENT '来源：post_video/profile_video/other',
  `platform` varchar(32) DEFAULT NULL COMMENT '来源平台',
  `account_id` varchar(128) DEFAULT NULL COMMENT '关联账号ID',
  `post_id` varchar(128) DEFAULT NULL COMMENT '关联发文ID，对应 collect_posts.content_id',
  `profile_id` varchar(128) DEFAULT NULL COMMENT '关联主页账号ID',
  `origin_url` text COMMENT '原始视频直链URL',
  `local_path` varchar(512) DEFAULT NULL COMMENT '本地视频路径',
  `content_sha256` char(64) DEFAULT NULL COMMENT '视频SHA-256',
  `mime_type` varchar(64) DEFAULT NULL COMMENT '视频MIME',
  `file_size` bigint DEFAULT NULL COMMENT '视频字节数',
  `duration_sec` decimal(10,2) DEFAULT NULL COMMENT '时长秒',
  `width` int DEFAULT NULL COMMENT '宽',
  `height` int DEFAULT NULL COMMENT '高',
  `storage_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/downloading/stored/failed',
  `analyze_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/skipped',
  `frame_interval_sec` decimal(6,2) NOT NULL DEFAULT '3.00' COMMENT '抽帧间隔秒，默认3',
  `frame_extracted_cnt` int NOT NULL DEFAULT '0' COMMENT '抽帧总数',
  `frame_analyzed_cnt` int NOT NULL DEFAULT '0' COMMENT '成功分析帧数',
  `frame_stored_cnt` int NOT NULL DEFAULT '0' COMMENT '长期落盘帧数',
  `analysis_json` json DEFAULT NULL COMMENT '全部帧分析结果列表',
  `video_analysis_text` mediumtext COMMENT '整段视频综合分析正文',
  `video_analysis_json` json DEFAULT NULL COMMENT '整段视频结构化分析',
  `error_message` varchar(1000) DEFAULT NULL COMMENT '最近失败原因',
  `retry_count` int NOT NULL DEFAULT '0' COMMENT '重试次数',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  `stored_at` datetime(3) DEFAULT NULL COMMENT '视频落盘时间',
  `analyzed_at` datetime(3) DEFAULT NULL COMMENT '分析完成时间',
  PRIMARY KEY (`video_id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_status` (`task_id`,`analyze_status`),
  KEY `idx_account` (`task_id`,`platform`,`account_id`),
  KEY `idx_post` (`task_id`,`platform`,`post_id`),
  KEY `idx_sha256` (`content_sha256`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='视频资产与整段/逐帧分析结果';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cross_platform_candidates`
--

DROP TABLE IF EXISTS `cross_platform_candidates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cross_platform_candidates` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `platform` varchar(32) NOT NULL COMMENT '候选账号所在平台，如 weibo、bilibili、twitter',
  `account_id` varchar(128) NOT NULL COMMENT '平台内账号唯一 ID',
  `account_handle` varchar(256) DEFAULT NULL COMMENT '账号展示名或 @handle',
  `confidence` decimal(5,4) DEFAULT NULL COMMENT '匹配置信度 0～1',
  `evidence_json` json DEFAULT NULL COMMENT '匹配依据 JSON，如昵称相同、简介含相同链接',
  `match_strategy` varchar(64) DEFAULT NULL COMMENT '匹配策略：maigret / nickname 昵称 / bio_link 简介链接 等',
  `status` varchar(16) NOT NULL DEFAULT 'candidate' COMMENT '候选状态：candidate 候选 / excluded 已排除 / weak 弱线索',
  `raw_json` json DEFAULT NULL COMMENT '平台返回的原始候选对象 JSON',
  `tool_output_id` bigint DEFAULT NULL COMMENT '关联 hermes_tool_outputs.id，可追溯来源调用',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '入库时间',
  PRIMARY KEY (`id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_platform` (`task_id`,`platform`)
) ENGINE=InnoDB AUTO_INCREMENT=155 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='跨平台候选账号表：阶段3 检索到的疑似同人账号';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hermes_agent_l4_detail`
--

DROP TABLE IF EXISTS `hermes_agent_l4_detail`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `hermes_agent_l4_detail` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `node_id` varchar(128) NOT NULL COMMENT 'ES L4 节点 id，如 cap_agent_twitter_posts',
  `node_name` varchar(128) NOT NULL COMMENT '节点中文名（冗余，便于核对）',
  `parent_agent_id` varchar(128) NOT NULL COMMENT '所属 L3 agent id',
  `intro` text NOT NULL COMMENT '简介',
  `system_help` text NOT NULL COMMENT '对系统的帮助',
  `text_example` text NOT NULL COMMENT '文字示例',
  `image_examples` json NOT NULL COMMENT '图片示例 URL 数组，如 ["url1","url2"]',
  `image_row_keys` json NOT NULL COMMENT 'HBase 原图 RowKey 有序数组，如 ["l4:node:01","l4:node:02"]',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_node_id` (`node_id`),
  KEY `idx_parent_agent` (`parent_agent_id`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='大屏 L4 节点详情展示数据';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hermes_tasks`
--

DROP TABLE IF EXISTS `hermes_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `hermes_tasks` (
  `task_id` varchar(64) NOT NULL COMMENT '任务唯一ID，Java 生成 UUID',
  `task_type` varchar(32) NOT NULL DEFAULT 'account_collect' COMMENT '任务类型，01 固定为 account_collect（账号信息采集）',
  `session_id` varchar(64) DEFAULT NULL COMMENT 'Hermes 会话 ID，对接 Agent 时使用',
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '任务状态：pending 待执行 / running 执行中 / completed 已完成 / failed 失败',
  `current_phase` varchar(32) DEFAULT NULL COMMENT '当前执行阶段：resolve_seed 解析种子 / cross_platform 跨平台检索 / verify 真实性核验 / stream_gen 特征流生成 / stream_validate 流校验 / account_finalize 账号收敛 / collect 分平台采集 / done 结束',
  `cross_platform` tinyint(1) DEFAULT NULL COMMENT '是否跨平台采集：1 是 / 0 否，由 Java 根据前端点选写入',
  `seed_json` json DEFAULT NULL COMMENT '种子账号 JSON：platform 平台、account_hint 用户输入、account_id 解析后平台ID 等',
  `subject_json` json DEFAULT NULL COMMENT '任务扩展参数 JSON，备用',
  `error_message` text COMMENT '失败时的错误信息',
  `started_at` datetime(3) DEFAULT NULL COMMENT '任务开始执行时间',
  `finished_at` datetime(3) DEFAULT NULL COMMENT '任务结束时间',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间',
  `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录最后更新时间',
  PRIMARY KEY (`task_id`),
  KEY `idx_status` (`status`),
  KEY `idx_phase` (`current_phase`),
  KEY `idx_session` (`session_id`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='总流程状态表：一次账号采集任务的全局状态与阶段';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hermes_thought_events`
--

DROP TABLE IF EXISTS `hermes_thought_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `hermes_thought_events` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` varchar(64) NOT NULL COMMENT '所属任务ID',
  `seq` int NOT NULL COMMENT '与 SSE 同一单调序号',
  `event_type` varchar(64) NOT NULL DEFAULT 'tool.progress' COMMENT '事件类型',
  `tool_name` varchar(128) NOT NULL DEFAULT '_thinking' COMMENT '工具名，思考整句为 _thinking',
  `content` varchar(2048) NOT NULL COMMENT '整句进度文案（截断）',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_seq` (`task_id`,`seq`),
  KEY `idx_task_seq` (`task_id`,`seq`),
  CONSTRAINT `fk_hermes_thought_events_task` FOREIGN KEY (`task_id`) REFERENCES `hermes_tasks` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='思考流精简事件（_thinking 整句，供历史/刷新回放）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hermes_tool_outputs`
--

DROP TABLE IF EXISTS `hermes_tool_outputs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `hermes_tool_outputs` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `phase` varchar(64) DEFAULT NULL COMMENT '工具调用归属步骤键，与 collect_phase_steps.step_key 一致，如 step1_seed / step6_post_twitter',
  `mcp_server` varchar(64) DEFAULT NULL COMMENT 'MCP 服务名，如 weibo、twitter、maigret',
  `tool_name` varchar(128) NOT NULL COMMENT '工具全名，如 mcp_weibo_get_profile',
  `tool_args` json DEFAULT NULL COMMENT '工具入参 JSON',
  `tool_output` longtext NOT NULL COMMENT 'MCP 返回的完整原始 JSON，审计真源，不截断',
  `tool_call_id` varchar(128) NOT NULL COMMENT 'Hermes 工具调用唯一 ID，防重复入库',
  `duration_ms` int DEFAULT NULL COMMENT '调用耗时（毫秒）',
  `status` varchar(16) DEFAULT NULL COMMENT '调用结果：success 成功 / error 失败',
  `executed_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '工具执行完成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tool_call` (`tool_call_id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_tool` (`tool_name`),
  KEY `idx_phase` (`task_id`,`phase`)
) ENGINE=InnoDB AUTO_INCREMENT=228 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='MCP 工具调用表：每次 MCP 调用的完整原始输出';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hermes_user_dialogues`
--

DROP TABLE IF EXISTS `hermes_user_dialogues`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `hermes_user_dialogues` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `task_id` varchar(64) NOT NULL COMMENT '关联任务 ID',
  `session_id` varchar(64) DEFAULT NULL COMMENT 'Hermes 会话 ID',
  `role` varchar(16) NOT NULL COMMENT '消息角色：user 用户 / assistant 助手 / system 系统',
  `content` text NOT NULL COMMENT '消息正文，含用户一句话或系统回复',
  `payload_json` json DEFAULT NULL COMMENT '前端传入的原始请求 JSON（原样存储）',
  `msg_type` varchar(32) NOT NULL DEFAULT 'user_input' COMMENT '消息类型：user_input 用户输入 / assistant_reply 助手回复 / phase_progress 阶段进度 / summary 结果摘要',
  `report_tags` json DEFAULT NULL COMMENT '成报主题标签 JSON 数组，如 ["实名","家庭","涉华"]，仅 summary 行',
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '消息时间',
  PRIMARY KEY (`id`),
  KEY `idx_task` (`task_id`),
  KEY `idx_task_time` (`task_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户对话表：记录用户一句话及系统关键回复';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schema_migrations`
--

DROP TABLE IF EXISTS `schema_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `schema_migrations` (
  `version` varchar(32) NOT NULL COMMENT '迁移脚本版本号',
  `applied_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '执行时间',
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='SQL 迁移版本记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping routines for database 'hermes-xa'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-05 14:06:58
