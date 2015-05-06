# NUSync (a.k.a. NUS IVLE Syncer 2)

NUSync is a tool to help NUS students to get their course materials automatically in their cloud drives. The files are retrieved from IVLE Workbins and uploaded to users' cloud drives.

We would appreciate any help! If you find any bugs / have improvement suggestions, please feel free to contact us at support@sshz.org or simply create an issue here.


## Running Environment / Requirements

* Python 3 / PIP (Developed using Python 3.4.3)
* Redis >= 2.6.0 (Required by RQ)
* Supervisord to run the workers and scheduler

Run `pip install -f requirements.txt` to install the requirements. Note that `urllib3` is fetched from its git repository instead of PyPi because we need the newest version for Python 3 support.

The required processes are (supervised ):

* `gunicorn ivled2_webapp.py` to run the front-end web app.
* `python scheduler.py` to run the scheduler.
* Several `rqworker file user` to transport the files.
* At least one `rqworker user` to prevent starvation of user queue.

## Developers' Guide

We have to admit that there are a lot of dirty hacks / workarounds in our code. A significant portion of the current code is having a terrible coupling and we hope we can solve that soon.

If you would like to help us by adding support for other cloud service providers, we are very happy to hear that! Though we suggest you to start in next semester (AY 2015/16 SEM1) since our code cleaning should have done by then. (And also can test easier)

For your information, currently code for cloud storage support are put in both `drivers.py` and `ivled2_webapp.py` so it is quite messy. We are going to reorganize them and put everything into `drivers.py` so it will be easier to add new ones.
