import math

def _sync_from_v1_to_v2(wrapper_obj):
    wrapper_obj.r = math.sqrt(wrapper_obj.x**2 + wrapper_obj.y**2)
    wrapper_obj.theta = math.atan2(wrapper_obj.y, wrapper_obj.x)

def _sync_from_v2_to_v1(wrapper_obj):
    wrapper_obj.x = wrapper_obj.r * math.cos(wrapper_obj.theta)
    wrapper_obj.y = wrapper_obj.r * math.sin(wrapper_obj.theta)
