# CMake generated Testfile for 
# Source directory: /home/neil/Workspace/self-driving-golf-cart/src/open_street_map/osm_cartography
# Build directory: /home/neil/Workspace/self-driving-golf-cart/build/open_street_map/osm_cartography
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(_ctest_osm_cartography_nosetests_tests.test_geo_map.py "/home/neil/Workspace/self-driving-golf-cart/build/catkin_generated/env_cached.sh" "/usr/bin/python" "/opt/ros/kinetic/share/catkin/cmake/test/run_tests.py" "/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/nosetests-tests.test_geo_map.py.xml" "--return-code" "/usr/bin/cmake -E make_directory /home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography" "/usr/bin/nosetests-2.7 -P --process-timeout=60 /home/neil/Workspace/self-driving-golf-cart/src/open_street_map/osm_cartography/tests/test_geo_map.py --with-xunit --xunit-file=/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/nosetests-tests.test_geo_map.py.xml")
add_test(_ctest_osm_cartography_nosetests_tests.test_xml_map.py "/home/neil/Workspace/self-driving-golf-cart/build/catkin_generated/env_cached.sh" "/usr/bin/python" "/opt/ros/kinetic/share/catkin/cmake/test/run_tests.py" "/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/nosetests-tests.test_xml_map.py.xml" "--return-code" "/usr/bin/cmake -E make_directory /home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography" "/usr/bin/nosetests-2.7 -P --process-timeout=60 /home/neil/Workspace/self-driving-golf-cart/src/open_street_map/osm_cartography/tests/test_xml_map.py --with-xunit --xunit-file=/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/nosetests-tests.test_xml_map.py.xml")
add_test(_ctest_osm_cartography_roslaunch-check_launch "/home/neil/Workspace/self-driving-golf-cart/build/catkin_generated/env_cached.sh" "/usr/bin/python" "/opt/ros/kinetic/share/catkin/cmake/test/run_tests.py" "/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/roslaunch-check_launch.xml" "--return-code" "/usr/bin/cmake -E make_directory /home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography" "/opt/ros/kinetic/share/roslaunch/cmake/../scripts/roslaunch-check -o '/home/neil/Workspace/self-driving-golf-cart/build/test_results/osm_cartography/roslaunch-check_launch.xml' '/home/neil/Workspace/self-driving-golf-cart/src/open_street_map/osm_cartography/launch' ")
