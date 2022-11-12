-- SQL dump generated using DBML (dbml-lang.org)
-- Database: MySQL
-- Generated at: 2022-11-12T21:56:19.683Z

CREATE TABLE `participant` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `competition_id` int NOT NULL,
  `sheet_id` varchar(255) NOT NULL,
  `paid` bit,
  `created_at` timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE `competition` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` varchar(255) NOT NULL,
  `entry_fee` int NOT NULL
);

CREATE TABLE `prediction` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_score` int NOT NULL,
  `away_score` int NOT NULL,
  `match_id` int NOT NULL,
  `participant_id` int NOT NULL
);

CREATE TABLE `match` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_team` varchar(255) NOT NULL,
  `away_team` varchar(255) NOT NULL,
  `kickoff` timestamp NOT NULL,
  `livescore_id` int
);

CREATE TABLE `score` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_score` int NOT NULL,
  `away_score` int NOT NULL,
  `match_id` int NOT NULL,
  `source` varchar(255)
);

CREATE UNIQUE INDEX `participant_index_0` ON `participant` (`email`, `competition_id`);

CREATE INDEX `match_id_index` ON `prediction` (`match_id`);

CREATE INDEX `participant_id_index` ON `prediction` (`participant_id`);

CREATE INDEX `livescore_id_index` ON `match` (`livescore_id`);

CREATE INDEX `match_id_index` ON `score` (`match_id`);

ALTER TABLE `participant` ADD FOREIGN KEY (`competition_id`) REFERENCES `competition` (`id`);

ALTER TABLE `prediction` ADD FOREIGN KEY (`participant_id`) REFERENCES `participant` (`id`);

ALTER TABLE `prediction` ADD FOREIGN KEY (`match_id`) REFERENCES `match` (`id`);

ALTER TABLE `score` ADD FOREIGN KEY (`match_id`) REFERENCES `match` (`id`);
