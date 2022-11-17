-- SQL dump generated using DBML (dbml-lang.org)
-- Database: MySQL
-- Generated at: 2022-11-16T20:44:34.989Z

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

CREATE TABLE `match_prediction` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_score` int NOT NULL,
  `away_score` int NOT NULL,
  `match_id` int NOT NULL,
  `participant_id` int NOT NULL
);

CREATE TABLE `team_prediction` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `team` varchar(255) NOT NULL,
  `stage` varchar(255) NOT NULL,
  `order` int,
  `participant_id` int NOT NULL
);

CREATE TABLE `fixtures` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_team` varchar(255) NOT NULL,
  `away_team` varchar(255) NOT NULL,
  `kickoff` timestamp NOT NULL,
  `livescore_id` int NOT NULL,
  `stage` varchar(255) NOT NULL
);

CREATE TABLE `score` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `home_score` int NOT NULL,
  `away_score` int NOT NULL,
  `match_id` int NOT NULL,
  `source` varchar(255)
);

CREATE UNIQUE INDEX `participant_index_0` ON `participant` (`email`, `competition_id`);

CREATE INDEX `match_id_index` ON `match_prediction` (`match_id`);

CREATE INDEX `participant_id_index` ON `match_prediction` (`participant_id`);

CREATE UNIQUE INDEX `livescore_id_index` ON `fixtures` (`livescore_id`);

CREATE UNIQUE INDEX `match_id_index` ON `score` (`match_id`);

ALTER TABLE `participant` ADD FOREIGN KEY (`competition_id`) REFERENCES `competition` (`id`);

ALTER TABLE `match_prediction` ADD FOREIGN KEY (`participant_id`) REFERENCES `participant` (`id`);

ALTER TABLE `team_prediction` ADD FOREIGN KEY (`participant_id`) REFERENCES `participant` (`id`);

ALTER TABLE `match_prediction` ADD FOREIGN KEY (`match_id`) REFERENCES `fixtures` (`id`);

ALTER TABLE `score` ADD FOREIGN KEY (`match_id`) REFERENCES `fixtures` (`id`);
