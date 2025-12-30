# TurtleBot3 Cleaner

## Overview
TurtleBot3 Cleaner is a ROS package for autonomous cleaning tasks in a simulated house environment.  
The robot navigates through rooms, reads QR codes to identify each room, and performs cleaning tasks in a predefined order.

---

## Features
- Autonomous room navigation using `move_base`.
- QR code recognition with OpenCV.
- Custom room orders.
- Automatic room-specific cleaning reports.

---

## Prerequisites

### ROS
- ROS Noetic.

### ROS Packages
Ensure the following packages are installed:
- `turtlebot3`
- `turtlebot3_gazebo`
- `turtlebot3_navigation`
- `turtlebot3_teleop`
- `turtlebot3_slam`

---

## Installation
Clone the repository into your catkin workspace and build:

```bash
cd ~/catkin_ws/src
git clone https://github.com/user/turtlebot3_cleaner.git
cd ~/catkin_ws
catkin_make
source devel/setup.bash

Usage
1. Launch Gazebo with the custom house world

roslaunch turtlebot3_cleaner my_house.launch
2. Launch SLAM with RViz

roslaunch turtlebot3_cleaner slam.launch slam_methods:=gmapping
3. Save the map
In another terminal, while SLAM is running:


rosrun map_server map_saver -f $(rospack find turtlebot3_cleaner)/maps/map2
4. Launch Navigation with the saved map

roslaunch turtlebot3_cleaner nav.launch
Or to open a specific map:

roslaunch turtlebot3_cleaner nav.launch map_file:=$(rospack find turtlebot3_cleaner)/maps/map2.yaml
5. Launch the cleaner nodes
This launch file starts both the QR reader and task manager nodes simultaneously:


roslaunch turtlebot3_cleaner cleaner.launch room_order:="['LIVINGROOM','CORRIDOR','BEDROOM','GUESTROOM']"
Notes
The room_order parameter defines the order in which the robot visits rooms.
Leave it blank to use the default order: 'LIVINGROOM','BEDROOM','KITCHEN','CORRIDOR','GUESTROOM'.

The robot will generate a cleaning report in the package root after completing tasks.