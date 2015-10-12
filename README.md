# jenkins-status-light

Hackathon project that will poll the current build status of jenkins and change the LED lights accordingly. 

Simply supply the jenkins host and job name to poll as command line arguments:

$ sudo python jenkins_status_light.py --jenkins-url https://jenkins.example.com --job job-name

Note: I'm using optparse and python 2.6, but you'll probably want to use argparse if using newer versions of Python since optparse is now depreciated.
