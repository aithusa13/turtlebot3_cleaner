#!/usr/bin/env python3
import rospy
import yaml
import actionlib
import math
import rospkg
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped
from tf.transformations import quaternion_from_euler

class TaskManager:
    def __init__(self):
        rospy.init_node("task_manager")

        self.current_qr = None
        self.qr_listening = False
        self.expected_qr = None
        self.finish_pub = rospy.Publisher("/task_finished", String, queue_size=1)
        self.room_order = rospy.get_param("~room_order", None)
        if self.room_order:
            try:
                self.room_order = yaml.safe_load(self.room_order)
            except Exception as e:
                rospy.logwarn("failed to parse room_order string: %s", e)
                self.room_order = None        
        self.report = {}  

        self.move_base = actionlib.SimpleActionClient(
            "move_base", MoveBaseAction
        )

        rospy.loginfo("waiting for move_base")
        self.move_base.wait_for_server()
        rospy.loginfo("move_base is working")

        rospy.loginfo("waiting for map")
        rospy.wait_for_message("/map", OccupancyGrid)
        rospy.loginfo("map loaded")

        rospy.Subscriber("/current_room", String, self.qr_callback)

        self.rooms = self.get_waypoints()

        rospy.loginfo("task manager ready")
        self.clean()

    def get_waypoints(self):
        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path("turtlebot3_cleaner")

        waypoint_file = rospy.get_param(
            "~waypoint_file",
            pkg_path + "/config/waypoints.yaml"
        )

        with open(waypoint_file, "r") as f:
            data = yaml.safe_load(f)

        rooms = data["rooms"]

        if self.room_order:
            rospy.loginfo("room order: %s", self.room_order)

            ordered_rooms = []
            for name in self.room_order:
                found = False
                for room in rooms:
                    if room["name"] == name:
                        ordered_rooms.append(room)
                        found = True
                        break
                if not found:
                    rospy.logwarn("room %s not found in yaml!", name)

            return ordered_rooms

        rospy.loginfo("using the default room order")
        return rooms

    def qr_callback(self, msg):
        if not self.qr_listening:
            return

        if msg.data != self.expected_qr:
            return

        self.current_qr = msg.data
        self.qr_listening = False
        rospy.loginfo("qr scanning done: %s", msg.data)


    def handle_qr_step(self, room, max_retry=3, yaw=0.3):
        self.expected_qr = room["qr_expected"]

        for attempt in range(1, max_retry + 1):
            rospy.loginfo(
                "qr scanning attempt %d/%d for room %s",
                attempt, max_retry, room["name"]
            )

            self.current_qr = None
            self.qr_listening = True

            start = rospy.Time.now()
            timeout = 10.0
            rate = rospy.Rate(10)

            while not rospy.is_shutdown():
                if self.current_qr is not None:
                    rospy.loginfo("qr verification done: %s", self.current_qr)
                    return True

                if (rospy.Time.now() - start).to_sec() > timeout:
                    rospy.logwarn("qr scanning timeout at room %s", room["name"])
                    self.qr_listening = False
                    break

                rate.sleep()

            if attempt == 1:
                self.send_goal(
                    room["qr_coordinate"]["x"],
                    room["qr_coordinate"]["y"],
                    room["qr_coordinate"]["yaw"] + yaw
                )
            elif attempt == 2:
                self.send_goal(
                    room["qr_coordinate"]["x"],
                    room["qr_coordinate"]["y"],
                    room["qr_coordinate"]["yaw"] - yaw
                )

        rospy.logwarn("qr verification failed for room %s", room["name"])
        return False

    def send_goal(self, x, y, yaw, max_retry=2):
        
        for attempt in range(1, max_retry + 1):
            rospy.loginfo(
                "sending goal (attempt %d/%d)", attempt, max_retry
            )

            goal = MoveBaseGoal()
            goal.target_pose.header.frame_id = "map"
            goal.target_pose.header.stamp = rospy.Time.now()

            q = quaternion_from_euler(0, 0, yaw)
            goal.target_pose.pose.position.x = x
            goal.target_pose.pose.position.y = y
            goal.target_pose.pose.orientation.x = q[0]
            goal.target_pose.pose.orientation.y = q[1]
            goal.target_pose.pose.orientation.z = q[2]
            goal.target_pose.pose.orientation.w = q[3]

            self.move_base.cancel_all_goals()
            rospy.sleep(0.2)

            self.move_base.send_goal(goal)
            self.move_base.wait_for_result()

            state = self.move_base.get_state()

            if state == 3:
                rospy.loginfo("waypoint reached")
                return True
            else:
                rospy.logwarn("move_base failed")

        rospy.logerr("failed to reach goal after %d attempts", max_retry)
        return False


    def clean(self):
        ROOM_TOTAL_TIMEOUT = 120

        for room in self.rooms:
            name = room["name"]
            rospy.loginfo("--- room: %s ---", name)

            start_room = rospy.Time.now() 

            e = room["entry_goal"]
            if not self.send_goal(e["x"], e["y"], e["yaw"]):
                rospy.logwarn("navigation failed at entry of %s", name)
                self.report[name] = "FAIL"
                continue

            if (rospy.Time.now() - start_room).to_sec() > ROOM_TOTAL_TIMEOUT:
                rospy.logwarn("room timeout: %s", name)
                self.report[name] = "TIMEOUT"
                continue

            qr = room["qr_coordinate"]
            if not self.send_goal(qr["x"], qr["y"], qr["yaw"]):
                rospy.logwarn("navigation failed at qr pose of %s", name)
                self.report[name] = "FAIL"
                continue

            if not self.handle_qr_step(room):
                rospy.logwarn("qr scanning failed, skipping room %s", name)
                self.report[name] = "SKIPPED"
                continue

            for wp in room["cleaning_goals"]:
                if (rospy.Time.now() - start_room).to_sec() > ROOM_TOTAL_TIMEOUT:
                    rospy.logwarn("room timeout: %s", name)
                    self.report[name] = "TIMEOUT"
                    break
                self.send_goal(wp["x"], wp["y"], wp["yaw"])

            if name not in self.report:  
                rospy.loginfo("%s cleaned successfully", name)
                self.report[name] = "SUCCESS"

        self.generate_report()
        self.finish_pub.publish("finished")
        rospy.loginfo("task finished message sent")


    def generate_report(self):
        rospy.loginfo("cleaning report")

        rospack = rospkg.RosPack()
        pkg_path = rospack.get_path("turtlebot3_cleaner")
        report_path = pkg_path + "/cleaning_report.txt"

        with open(report_path, "w") as f:
            f.write("CLEANING REPORT\n")
            f.write("---\n")

            for room, status in self.report.items():
                line = f"{room}: {status}"
                rospy.loginfo(line)
                f.write(line + "\n")

        rospy.loginfo("report saved to %s", report_path)


if __name__ == "__main__":
    TaskManager()
