create table if not exists aa_detections (
	id integer primary key autoincrement,
	datelogged integer not null
);

create table if not exists ab_setup (
	id integer primary key autoincrement,
	sitename text,
	cameracmd text,
	alarm_mode boolean,
	monitorstart date,
	monitorend	date,
	random_mode boolean, 
	photo_freq  integer
);

create table if not exists ac_imgcomments(
	id integer primary key autoincrement,
	imagename text,
	datetime date,
	comment text
);

