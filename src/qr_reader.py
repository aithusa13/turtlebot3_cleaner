#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2

class QRReader:
    def __init__(self):
        rospy.init_node('qr_reader_opencv')

        self.bridge = CvBridge()
        self.detector = cv2.QRCodeDetector()
        self.room_pub = rospy.Publisher("/current_room", String, queue_size=10)
        self.finish_sub = rospy.Subscriber("/task_finished", String, self.shutdown_callback)
        
        self.sub = rospy.Subscriber(
            "/camera/rgb/image_raw",
            Image,
            self.image_callback
        )

        self.window_created = False

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        data, bbox, _ = self.detector.detectAndDecode(cv_image)

        if bbox is None or len(bbox) == 0:
            return        

        if data:
            self.room_pub.publish(data)
            #rospy.loginfo_throttle(1.0, "QR code: %s", data)

        if not self.window_created:
            cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Camera", 400, 300)
            self.window_created = True

        cv2.imshow("Camera", cv_image)
        cv2.waitKey(1)

    def shutdown_callback(self, msg):
        rospy.loginfo("task completed, shutting down qr reader")
        rospy.signal_shutdown("task completed")

    def run(self):
        rospy.spin()


if __name__ == "__main__":
    reader = QRReader()
    reader.run()
