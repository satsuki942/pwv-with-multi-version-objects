def _sync_from_v1_to_v2(wrapper_obj):
    wrapper_obj._v2 = "Version 2"
    del wrapper_obj._v1

def _sync_from_v2_to_v1(wrapper_obj):
    wrapper_obj._v1 = "Version 1"
    del wrapper_obj._v2