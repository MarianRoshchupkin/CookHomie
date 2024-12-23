.PHONY: initdb runbot resetdb

initdb:
	python manage.py initdb

runbot:
	python manage.py runbot

resetdb:
	python manage.py resetdb
