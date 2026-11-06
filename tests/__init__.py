import faulthandler
import os

# On CI a test that hangs (for example one waiting for a window that never appears) would stall the job until GitHub
# cancels it without saying where. Print every thread's stack and stop instead.
if os.environ.get("CI"):
    faulthandler.dump_traceback_later(int(os.environ.get("TEST_HANG_SECONDS", "600")), exit=True)
