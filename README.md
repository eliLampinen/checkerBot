Bot to inform availability of something with email. I don't want to specify what is this bot used for that's why the config file might include something that could be written to the script itself. Running this with cron on Linux server, currently every 5 minutes.

Bot checks the availability of something that is very rarely available. Then it sends the current availability with email. Current availability is stored in file so that the same availability is not sent multiple times in a row. However if the email receiver is not fast enough to book the slot and the slot becomes again available, the bot updates the availability file so that email is sent again.

If multiple errors occurs in the past 24 hours with the script, script sends email to admin user. Only 1 email is sent per day so not on every cron iteration.
