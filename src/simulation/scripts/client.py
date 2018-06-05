#!/usr/bin/env python

"""
ROS Bridge for carla

Using python2 for now (default setup for kinetic and lunar)
Project created by George Laurent

self-driving vehicle research platform
(c) Neil Nie, 2018. All Rights Reserved
Contact: contact@neilnie.com


"""

import math
import numpy as np
import random
import time
import copy
import cv2

import rosbag
import rospy
import tf
import helper
from carla.client import make_carla_client
from carla.sensor import Camera, Lidar, LidarMeasurement, Image
from carla.sensor import Transform as carla_Transform
from carla.settings import CarlaSettings
from carla import image_converter
from ackermann_msgs.msg import AckermannDrive
from cv_bridge import CvBridge
from geometry_msgs.msg import TransformStamped, Transform, Pose
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image as RosImage
from sensor_msgs.msg import PointCloud2, CameraInfo
from sensor_msgs.point_cloud2 import create_cloud_xyz32
from std_msgs.msg import Header
from tf2_msgs.msg import TFMessage
from visualization_msgs.msg import MarkerArray, Marker


WINDOW_WIDTH = 640
WINDOW_HEIGHT = 480
MINI_WINDOW_WIDTH = 640
MINI_WINDOW_HEIGHT = 480


class CarlaROSBridge(object):
    """
    Carla Ros bridge
    """
    def __init__(self, client, params, rate=15):
        """

        :param params: dict of parameters, see settings.yaml
        :param rate: rate to query data from carla in Hz
        """
        self.message_to_publish = []
        self.param_sensors = params['sensors']
        self.client = client
        self.carla_settings = CarlaSettings()
        self.carla_settings.set(
            SendNonPlayerAgentsInfo=True,
            NumberOfVehicles=20,
            NumberOfPedestrians=40,
            WeatherId=random.choice([1, 3, 7, 8, 14]),
            SynchronousMode=params['SynchronousMode'],
            QualityLevel=params['QualityLevel'])
        self.carla_settings.randomize_seeds()

        self.cv_bridge = CvBridge()

        self.cur_time = rospy.Time.from_sec(0)  # at the beginning of simulation
        self.carla_game_stamp = 0
        self.carla_platform_stamp = 0
        self.rate = rospy.Rate(rate)
        self.publishers = {}
        self._camera_infos = {}
        self.processes = []
        self.publishers['tf'] = rospy.Publisher("/tf", TFMessage, queue_size=100)
        self.publishers['vehicles'] = rospy.Publisher("/vehicles", MarkerArray, queue_size=10)
        self.publishers['vehicles_text'] = rospy.Publisher("/vehicles_text", MarkerArray, queue_size=10)
        self.publishers['player_vehicle'] = rospy.Publisher("/player_vehicle", Marker, queue_size=10)
        self.publishers['pedestrians'] = rospy.Publisher("/pedestrians", MarkerArray, queue_size=10)
        self.publishers['traffic_lights'] = rospy.Publisher("/traffic_lights", MarkerArray, queue_size=10)

        # default control command
        self.cur_control = {'steer': 0.0, 'throttle': 0.0, 'brake': 0.0, 'hand_brake': False, 'reverse': False}
        self.cmd_vel_subscriber = rospy.Subscriber('/ackermann_cmd', AckermannDrive, self.set_new_control_callback)
        self.world_link = 'map'
        self.sensors = {}
        self.tf_to_publish = []

        # ----------------------------------------------------------------

        camera0 = Camera('CameraRGB')
        camera0.set_image_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        camera0.set_position(2.0, 0.0, 1.4)
        camera0.set_rotation(0.0, 0.0, 0.0)
        self.carla_settings.add_sensor(camera0)
        self.sensors['CameraRGB'] = camera0  # we also add the sensor to our lookup
        topic_image = 'CameraRGB' + '/image_raw'
        topic_camera = 'CameraRGB' + '/camera_info'
        self.publishers[topic_image] = rospy.Publisher(topic_image, RosImage, queue_size=10)
        self.publishers[topic_camera] = rospy.Publisher(topic_camera, CameraInfo, queue_size=10)
        # computing camera info, when publishing update the stamp
        camera_info = CameraInfo()
        camera_info.header.frame_id = 'CameraRGB'
        camera_info.width = camera0.ImageSizeX
        camera_info.height = camera0.ImageSizeY
        self._camera_infos['CameraRGB'] = camera_info

        # ------------------------------------------------------------------

        camera1 = Camera('CameraDepth', PostProcessing='Depth')
        camera1.set_image_size(MINI_WINDOW_WIDTH, MINI_WINDOW_HEIGHT)
        camera1.set_position(2.0, 0.0, 1.4)
        camera1.set_rotation(0.0, 0.0, 0.0)
        self.carla_settings.add_sensor(camera1)
        self.sensors['CameraDepth'] = camera0  # we also add the sensor to our lookup
        topic_image = 'CameraDepth' + '/image_raw'
        topic_camera = 'CameraDepth' + '/camera_info'
        self.publishers[topic_image] = rospy.Publisher(topic_image, RosImage, queue_size=10)
        self.publishers[topic_camera] = rospy.Publisher(topic_camera, CameraInfo, queue_size=10)
        # computing camera info, when publishing update the stamp
        camera_info = CameraInfo()
        camera_info.header.frame_id = 'CameraDepth'
        camera_info.width = camera0.ImageSizeX
        camera_info.height = camera0.ImageSizeY
        self._camera_infos['CameraDepth'] = camera_info

        # -----------------------------------------------------------------

        camera2 = Camera('CameraSemSeg', PostProcessing='SemanticSegmentation')
        camera2.set_image_size(MINI_WINDOW_WIDTH, MINI_WINDOW_HEIGHT)
        camera2.set_position(2.0, 0.0, 1.4)
        camera2.set_rotation(0.0, 0.0, 0.0)
        self.carla_settings.add_sensor(camera2)
        self.sensors['CameraSemSeg'] = camera0  # we also add the sensor to our lookup
        topic_image = 'CameraSemSeg' + '/image_raw'
        topic_camera = 'CameraSemSeg' + '/camera_info'
        self.publishers[topic_image] = rospy.Publisher(topic_image, RosImage, queue_size=10)
        self.publishers[topic_camera] = rospy.Publisher(topic_camera, CameraInfo, queue_size=10)
        # computing camera info, when publishing update the stamp
        camera_info = CameraInfo()
        camera_info.header.frame_id = 'CameraSemSeg'
        camera_info.width = camera0.ImageSizeX
        camera_info.height = camera0.ImageSizeY
        self._camera_infos['CameraSemSeg'] = camera_info

        # -----------------------------------------------------------------

        lidar = Lidar('Lidar32')
        lidar.set_position(0, 0, 2.5)
        lidar.set_rotation(0, 0, 0)
        lidar.set(
            Channels=32,
            Range=50,
            PointsPerSecond=100000,
            RotationFrequency=10,
            UpperFovLimit=10,
            LowerFovLimit=-30)
        self.carla_settings.add_sensor(lidar)

        self.sensors['Lidar32'] = lidar  # we also add the sensor to our lookup
        self.publishers['Lidar32'] = rospy.Publisher('Lidar32', PointCloud2, queue_size=10)
        rospy.loginfo("lidar sensor added")
        # -------------------------------------------------------

    def set_new_control_callback(self, data):
        """
        Convert a Ackerman drive msg into carla control msg

        Right now the control is really simple and don't enforce acceleration and jerk command, nor the steering acceleration too
        :param data: AckermannDrive msg
        :return:
        """
        steering_angle_ctrl = data.steering_angle
        speed_ctrl = data.speed

        max_steering_angle = math.radians(500)  # 500 degrees is the max steering angle that I have on my car,
                                                #  would be nice if we could use the value provided by carla
        max_speed = 27  # just a value for me, 27 m/sec seems to be a reasonable max speed for now

        control = {}

        if abs(steering_angle_ctrl) > max_steering_angle:
            rospy.logerr("Max steering angle reached, clipping value")
            steering_angle_ctrl = np.clip(steering_angle_ctrl, -max_steering_angle, max_steering_angle)

        if abs(speed_ctrl) > max_speed:
            rospy.logerr("Max speed reached, clipping value")
            speed_ctrl = np.clip(speed_ctrl, -max_speed, max_speed)

        if speed_ctrl == 0:
            control['brake'] = True

        control['steer'] = steering_angle_ctrl / max_steering_angle
        control['throttle'] = abs(speed_ctrl / max_speed)
        control['reverse'] = True if speed_ctrl < 0 else False

        self.cur_control = control

    def send_msgs(self):
        """
        Publish all message store then clean the list of message to publish
        :return:
        """
        for name, message in self.message_to_publish:
            self.publishers[name].publish(message)
        self.message_to_publish = []

    # def add_publishers(self):

        # for name, _ in self.param_sensors.items():
        #     self.add_sensor(name)

    def compute_cur_time_msg(self):
        self.message_to_publish.append(('clock', Clock(self.cur_time)))

    def compute_sensor_msg(self, name, sensor_data):

        if isinstance(sensor_data, Image):
            self.compute_camera_transform(name, sensor_data)
            self.compute_camera_sensor_msg(name, sensor_data)
        elif isinstance(sensor_data, LidarMeasurement):
            self.compute_lidar_transform(name, sensor_data)
            self.compute_lidar_sensor_msg(name, sensor_data)
        else:
            rospy.logerr("{}, {} is not handled yet".format(name, sensor_data))

    def compute_camera_sensor_msg(self, name, sensor):

        if sensor.type == 'Depth':
            # ROS PEP 0118 : Depth images are published as sensor_msgs/Image encoded as 32-bit float. Each pixel is a depth (along the camera Z axis) in meters.
            data = np.float32(sensor.data * 1000.0)  # in carla 1.0 = 1km
            encoding = 'passthrough'
        elif sensor.type == 'SemanticSegmentation':
            encoding = 'mono16'  # for semantic segmentation we use mono16 in order to be able to limit range in rviz
            data = np.uint16(sensor.data)
        else:
            encoding = 'rgb8'
            data = sensor.data
        img_msg = self.cv_bridge.cv2_to_imgmsg(data, encoding=encoding)
        img_msg.header.frame_id = name
        img_msg.header.stamp = self.cur_time
        self.message_to_publish.append((name + '/image_raw', img_msg))

        cam_info = self._camera_infos[name]
        cam_info.header = img_msg.header
        self.message_to_publish.append((name + '/camera_info', cam_info))

    def publish_rgb_camera_sensor_msg(self, image):

        # if sensor.type == 'Depth':
        #     # ROS PEP 0118 : Depth images are published as sensor_msgs/Image encoded as 32-bit float. Each pixel is a depth (along the camera Z axis) in meters.
        #     data = np.float32(sensor.data * 1000.0)  # in carla 1.0 = 1km
        #     encoding = 'passthrough'
        # elif sensor.type == 'SemanticSegmentation':
        #     encoding = 'mono16'  # for semantic segmentation we use mono16 in order to be able to limit range in rviz
        #     data = np.uint16(sensor.data)
        # else:
        data = image_converter.to_rgb_array(image)
        img_msg = self.cv_bridge.cv2_to_imgmsg(cv2.cvtColor(data, cv2.COLOR_BGR2RGB))
        img_msg.header.stamp = self.cur_time
        self.publishers['CameraRGB' + '/image_raw'].publish(img_msg)


    def compute_lidar_sensor_msg(self, name, sensor):

        header = Header()
        header.frame_id = name
        header.stamp = self.cur_time
        # we take the oposite of y axis (as lidar point are express in left handed coordinate system, and ros need right handed)
        # we need a copy here, because the data are read only in carla numpy array
        new_sensor_data = sensor.data.copy()
        new_sensor_data = -new_sensor_data
        # we also need to permute x and y , todo find why
        new_sensor_data = new_sensor_data[..., [1, 0, 2]]
        point_cloud_msg = create_cloud_xyz32(header, new_sensor_data)
        self.message_to_publish.append((name, point_cloud_msg))

    def compute_player_pose_msg(self, player_measurement):

        #print("Player measurement is {}".format(player_measurement))
        t = TransformStamped()
        t.header.stamp = self.cur_time
        t.header.frame_id = self.world_link
        t.child_frame_id = "base_link"
        t.transform = helper.carla_transform_to_ros_transform(carla_Transform(player_measurement.transform))
        header = Header()
        header.stamp = self.cur_time
        header.frame_id = self.world_link
        marker = helper.get_vehicle_marker(player_measurement, header=header, agent_id=0, player=True)
        self.message_to_publish.append(('player_vehicle', marker))
        self.tf_to_publish.append(t)

    def compute_non_player_agent_msg(self, non_player_agents):
        """

        :param non_player_agents: list of carla_server_pb2.Agent return by carla API,
        with field 'id', 'vehicle', 'pedestrian', 'traffic_light', 'speed_limit_sign'

        :return:
        """
        vehicles = [(agent.id, agent.vehicle) for agent in non_player_agents if agent.HasField('vehicle')]
        pedestrians = [(agent.id, agent.pedestrian) for agent in non_player_agents if agent.HasField('pedestrian')]
        traffic_lights = [(agent.id, agent.traffic_light) for agent in non_player_agents if agent.HasField('traffic_light')]

        # TODO: add traffic signs
        #traffic_lights = [(agent.id, agent.traffic_light) for agent in non_player_agents if agent.HasField('traffic_light')]

        header = Header(stamp=self.cur_time, frame_id=self.world_link)

        self.compute_vehicle_msgs(vehicles, header)
        #self.compute_pedestrian_msgs(pedestrians)
        #self.compute_traffic_light_msgs(traffic_lights)

    def compute_vehicle_msgs(self, vehicles, header, agent_id=8):
        """
        Add MarkerArray msg for vehicle to the list of message to be publish

        :param vehicles: list of carla pb2 vehicle
        """
        if not(vehicles):
            return

        markers = [helper.get_vehicle_marker(vehicle, header, agent_id) for agent_id, vehicle in vehicles]
        marker_array = MarkerArray(markers)
        self.message_to_publish.append(('vehicles', marker_array))

        # adding text in rviz (TODO: refactor)
        markers_text = [copy.copy(marker) for marker in markers]
        for marker in markers_text:
            marker.type = Marker.TEXT_VIEW_FACING

        marker_array = MarkerArray(markers_text)
        self.message_to_publish.append(('vehicles_text', marker_array))

    def run(self):

        # creating ros publishers, and adding sensors to carla settings
        # self.add_publishers()

        self.publishers['clock'] = rospy.Publisher("clock", Clock, queue_size=10)

        # load settings into the server
        print(self.carla_settings)
        scene = self.client.load_settings(self.carla_settings)

        # Choose one player start at random.
        number_of_player_starts = len(scene.player_start_spots)
        player_start = random.randint(0, max(0, number_of_player_starts - 1))

        # start
        self.client.start_episode(player_start)

        while not rospy.is_shutdown():

            measurements, sensor_data = self.client.read_data()

            self.carla_game_stamp = measurements.game_timestamp
            self.carla_platform_stamp = measurements.platform_timestamp
            self.cur_time = rospy.Time.from_sec(self.carla_game_stamp * 1000.0)
            self.compute_cur_time_msg()

            # TODO: fix this bug
            # self.compute_player_pose_msg(measurements.player_measurements)
            # self.compute_non_player_agent_msg(measurements.non_player_agents)
            self.send_msgs()
            # data = sensor_data.get('CameraRGB', None)
            # if data is not None:
            #     self.publish_rgb_camera_sensor_msg(data)
            # #
            for name, sensor in sensor_data.items():
                self.compute_sensor_msg(name, sensor)

            tf_msg = TFMessage(self.tf_to_publish)
            self.publishers['tf'].publish(tf_msg)
            self.tf_to_publish = []

            if rospy.get_param('carla_autopilot', True):
                control = measurements.player_measurements.autopilot_control
                self.client.send_control(control)
            else:
                control = self.cur_control
                self.client.send_control(**control)

    def compute_camera_transform(self, name, sensor_data):
        parent_frame_id = "base_link"
        child_frame_id = name

        t = TransformStamped()
        t.header.stamp = self.cur_time
        t.header.frame_id = parent_frame_id
        t.child_frame_id = child_frame_id

        # for camera we reorient it to look at the same axis as the opencv projection
        # in order to get easy depth cloud for rgbd camera
        t.transform = helper.carla_transform_to_ros_transform(self.sensors[name].get_transform())

        rotation = t.transform.rotation
        quat = [rotation.x, rotation.y, rotation.z, rotation.w]
        roll, pitch, yaw = tf.transformations.euler_from_quaternion(quat)

        roll -= math.pi/2.0
        yaw -= math.pi/2.0

        quat = tf.transformations.quaternion_from_euler(roll, pitch, yaw)

        t.transform.rotation.x = quat[0]
        t.transform.rotation.y = quat[1]
        t.transform.rotation.z = quat[2]
        t.transform.rotation.w = quat[3]

        self.tf_to_publish.append(t)

    def compute_lidar_transform(self, name, sensor_data):
        parent_frame_id = "base_link"
        child_frame_id = name

        t = TransformStamped()
        t.header.stamp = self.cur_time
        t.header.frame_id = parent_frame_id
        t.child_frame_id = child_frame_id
        t.transform = helper.carla_transform_to_ros_transform(self.sensors[name].get_transform())

        self.tf_to_publish.append(t)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        rospy.loginfo("Exiting Bridge")
        return None


class CarlaROSBridgeWithBag(CarlaROSBridge):
    def __init__(self, *args, **kwargs):
        super(CarlaROSBridgeWithBag, self).__init__(*args, **kwargs)
        timestr = time.strftime("%Y%m%d-%H%M%S")
        self.bag = rosbag.Bag('/tmp/output_{}.bag'.format(timestr), mode='w')

    def send_msgs(self):
        for name, msg in self.message_to_publish:
            self.bag.write(name, msg, self.cur_time)

        super(CarlaROSBridgeWithBag, self).send_msgs()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        rospy.loginfo("Closing the bag file")
        self.bag.close()
        super(CarlaROSBridgeWithBag, self).__exit__(exc_type, exc_value, traceback)


if __name__ == "__main__":
    rospy.init_node("carla_client", anonymous=True)
    params = rospy.get_param('carla')
    host = params['host']
    port = params['port']

    rospy.loginfo("Trying to connect to {host}:{port}".format(host=host, port=port))

    with make_carla_client(host, port) as client:
        rospy.loginfo("Connection is ok")

        bridge_cls = CarlaROSBridgeWithBag if rospy.get_param('enable_rosbag') else CarlaROSBridge
        with bridge_cls(client=client, params=params) as carla_ros_bridge:
            carla_ros_bridge.run()
