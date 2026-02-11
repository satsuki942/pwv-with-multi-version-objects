def _sync_from_v1_to_v2(wrapper_obj):
    wrapper_obj._value2 = wrapper_obj._value1
    del wrapper_obj._value1

def _sync_from_v2_to_v1(wrapper_obj):
    wrapper_obj._value1 = wrapper_obj._value2
    del wrapper_obj._value2
