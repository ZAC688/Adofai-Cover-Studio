import pytest

from tools.test_android_device import Device, EXPECTED_NATIVE, verify_instrumentation


@pytest.mark.parametrize('serial', ['phone-12345', '1234567890', 'emulator-5562;anything'])
def test_native_test_runner_rejects_physical_or_malformed_targets_before_adb(serial):
    with pytest.raises(ValueError, match='Only an isolated emulator'):
        Device(serial)


def successful_protocol():
    # Parser unit fixture only; actual Android execution is separately recorded.
    return '\n'.join(f'INSTRUMENTATION_STATUS: class=com.zac688.adofaicoverstudio.{group}\n'
                     f'INSTRUMENTATION_STATUS: test={name}\nINSTRUMENTATION_STATUS_CODE: 0'
                     for group, name in sorted(EXPECTED_NATIVE))+f'\nOK ({len(EXPECTED_NATIVE)} tests)'


def test_native_protocol_requires_every_named_test_to_report_real_success():
    assert verify_instrumentation(successful_protocol()) == 9


@pytest.mark.parametrize('bad_output', [
    'OK (8 tests)',
    successful_protocol().replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -3', 1),
    successful_protocol().replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -4', 1),
    successful_protocol()+'\nINSTRUMENTATION_ABORTED: process crashed',
    successful_protocol().replace('actualEmbeddedChartFramePreviewsNativeGoldTrack', 'someOtherTest'),
])
def test_native_protocol_cannot_count_skipped_missing_or_aborted_checks_as_passed(bad_output):
    with pytest.raises(AssertionError):
        verify_instrumentation(bad_output)


@pytest.mark.parametrize('actual,expected,accepted', [(4096,16384,False),(16384,4096,False),(16384,16384,True),(4096,4096,True)])
def test_page_size_gate_cannot_report_the_wrong_emulator_as_a_native_pass(monkeypatch,actual,expected,accepted):
    device=Device('emulator-5564')
    values={('get-state',):'device',('shell','getprop','ro.kernel.qemu'):'1',
            ('shell','getprop','sys.boot_completed'):'1',('shell','getconf','PAGE_SIZE'):str(actual),
            ('shell','getprop','ro.build.version.sdk'):'35',('shell','getprop','ro.product.cpu.abi'):'x86_64'}
    monkeypatch.setattr(device,'adb',lambda *args: values[args])
    if accepted:
        assert device.validate(expected)=={'pageSize':actual,'sdk':'35','abi':'x86_64'}
    else:
        with pytest.raises(ValueError,match='tests were not run'):
            device.validate(expected)
