# CCTV People Counting
##### _by **duovision**_

[![duovision](https://github.com/user-attachments/assets/87e91980-75c3-4fd3-a8a0-ac020a777483)](https://s.id/duovision)

CCTV People Counting is an application developed to monitor the number of people density in a place by counting the number of people entering and leaving a location and detecting people seen by CCTV cameras by combining object detection and people counting algorithms based on the YOLO (You Only Look Once) model. 

## Tech Stacks

- Django 5.0
- Celery 5.4
- YOLO v8
- MySQL
- Redis Broker
- OpenCV
- And other libraries... (check the [requirements.txt](requirements.txt))

## Initializing The Project

After cloning the repository, ascertain you have Python 3.10 or newer and MySQL installed. Create a database named **'db_cctvproject'** (without the aposthropes).

## Installation

Enter the directory of the cloned repository. Make a Python Virtual Environment in the folder using
 ```
py -m venv venv
 ```
and then activate the virtual environment using
 ```
venv\Scripts\activate
 ```
 or use the command below if you are using unix system
 ```
 source venv\bin\activate
 ```
then finally run _setup.py_ to finish the installation process using the venv activated console as shown below
```
setup.py
```
## Running the Project.
You can run the project using the same console that use venv and run the _run.py_
```
run.py
```
and the website will run on [localhost port 8000](http://localhost:8000)
you can login using 
> username : admin123
> password : admin123

