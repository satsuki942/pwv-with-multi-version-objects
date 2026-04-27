import math

def _sync_from_v1_to_v2(wrapper_obj):
      wrapper_obj.log = wrapper_obj.log.replace('version 1', 'version 2')

def _sync_from_v2_to_v1(wrapper_obj):
      wrapper_obj.log = wrapper_obj.log.replace('version 2', 'version 1')
