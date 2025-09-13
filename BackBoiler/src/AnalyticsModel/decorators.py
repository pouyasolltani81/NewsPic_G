import functools
from AnalyticsModel.services import collect_system_metrics
from AnalyticsModel.models import SystemMetrics
from LogModel.log_handler import print_log


def gpu_check(min_memory):
    """
    Decorator to check if enough GPU memory is available based on latest SystemMetrics.
    - min_memory can be a number in GB (absolute) or a string with '%' (percentage of total memory free).
    - If not enough memory, skips function execution and logs via print_log.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the file path of the decorated function
            func_file_path = func.__code__.co_filename

            # Collect latest system metrics
            try:
                collect_system_metrics()
            except Exception as e:
                print_log(
                    user=None,
                    level='warning',
                    message=f"Could not collect system metrics: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )

            # Fetch latest metrics
            try:
                latest = SystemMetrics.objects.order_by('-timestamp').first()
                if not latest:
                    print_log(
                        user=None,
                        level='error',
                        message="No SystemMetrics data available. Skipping GPU check.",
                        exception_type='NoMetrics',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                # Check if GPU metrics are available
                if latest.gpu_total_memory_gb is None or latest.gpu_memory_usage is None:
                    print_log(
                        user=None,
                        level='error',
                        message="No GPU detected or GPU metrics not available. Skipping function.",
                        exception_type='NoGPUMetrics',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                total_gb = latest.gpu_total_memory_gb
                used_percent = latest.gpu_memory_usage
                free_gb = latest.gpu_free_memory_gb
                free_percent = latest.gpu_free_memory_percent

                # Check for percentage-based requirement
                if isinstance(min_memory, str) and min_memory.endswith('%'):
                    required_percent = float(min_memory.rstrip('%'))
                    if free_percent < required_percent:
                        print_log(
                            user=None,
                            level='error',
                            message=f"Not enough GPU memory: required {required_percent}%, available {free_percent:.2f}%. Skipping function.",
                            exception_type='InsufficientGPUMemory',
                            file_path=func_file_path,
                            view_name=func.__name__
                        )
                        return
                else:
                    # Check for absolute GB requirement
                    required_gb = float(min_memory)
                    if free_gb < required_gb:
                        print_log(
                            user=None,
                            level='error',
                            message=f"Not enough GPU memory: required {required_gb} GB, available {free_gb:.2f} GB. Skipping function.",
                            exception_type='InsufficientGPUMemory',
                            file_path=func_file_path,
                            view_name=func.__name__
                        )
                        return

            except Exception as e:
                print_log(
                    user=None,
                    level='error',
                    message=f"GPU memory check failed: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )
                return

            # Enough GPU memory, run the function
            return func(*args, **kwargs)

        return wrapper
    return decorator


def memory_check(min_memory):
    """
    Decorator to check if enough system RAM is available based on latest SystemMetrics.
    - min_memory can be a number in GB (absolute) or a string with '%' (percentage of total memory free).
    - If not enough memory, skips function execution and logs via print_log.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the file path of the decorated function
            func_file_path = func.__code__.co_filename

            # Collect latest system metrics
            try:
                collect_system_metrics()
            except Exception as e:
                print_log(
                    user=None,
                    level='warning',
                    message=f"Could not collect system metrics: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )

            # Fetch latest metrics
            try:
                latest = SystemMetrics.objects.order_by('-timestamp').first()
                if not latest:
                    print_log(
                        user=None,
                        level='error',
                        message="No SystemMetrics data available. Skipping memory check.",
                        exception_type='NoMetrics',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                total_gb = latest.total_memory_gb
                used_percent = latest.memory_usage
                free_gb = latest.system_free_memory_gb
                free_percent = latest.system_free_memory_percent

                # Check for percentage-based requirement
                if isinstance(min_memory, str) and min_memory.endswith('%'):
                    required_percent = float(min_memory.rstrip('%'))
                    if free_percent < required_percent:
                        print_log(
                            user=None,
                            level='error',
                            message=f"Not enough system memory: required {required_percent}%, available {free_percent:.2f}%. Skipping function.",
                            exception_type='InsufficientMemory',
                            file_path=func_file_path,
                            view_name=func.__name__
                        )
                        return
                else:
                    # Check for absolute GB requirement
                    required_gb = float(min_memory)
                    if free_gb < required_gb:
                        print_log(
                            user=None,
                            level='error',
                            message=f"Not enough system memory: required {required_gb} GB, available {free_gb:.2f} GB. Skipping function.",
                            exception_type='InsufficientMemory',
                            file_path=func_file_path,
                            view_name=func.__name__
                        )
                        return

            except Exception as e:
                print_log(
                    user=None,
                    level='error',
                    message=f"Memory check failed: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )
                return

            # Enough memory, run the function
            return func(*args, **kwargs)

        return wrapper
    return decorator


def cpu_check(max_usage_percent=80):
    """
    Decorator to check if CPU usage is below a threshold.
    - max_usage_percent: Maximum allowed CPU usage percentage (default 80%)
    - If CPU usage is too high, skips function execution and logs via print_log.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_file_path = func.__code__.co_filename

            try:
                collect_system_metrics()
            except Exception as e:
                print_log(
                    user=None,
                    level='warning',
                    message=f"Could not collect system metrics: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )

            try:
                latest = SystemMetrics.objects.order_by('-timestamp').first()
                if not latest:
                    print_log(
                        user=None,
                        level='error',
                        message="No SystemMetrics data available. Skipping CPU check.",
                        exception_type='NoMetrics',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                if latest.cpu_usage > max_usage_percent:
                    print_log(
                        user=None,
                        level='error',
                        message=f"CPU usage too high: current {latest.cpu_usage:.1f}%, max allowed {max_usage_percent}%. Skipping function.",
                        exception_type='HighCPUUsage',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

            except Exception as e:
                print_log(
                    user=None,
                    level='error',
                    message=f"CPU check failed: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )
                return

            return func(*args, **kwargs)

        return wrapper
    return decorator


def system_resources_check(min_memory=None, min_gpu_memory=None, max_cpu_percent=None):
    """
    Combined decorator to check multiple system resources.
    - min_memory: Minimum system RAM (GB or %)
    - min_gpu_memory: Minimum GPU memory (GB or %)
    - max_cpu_percent: Maximum CPU usage percentage
    All specified conditions must be met for the function to execute.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_file_path = func.__code__.co_filename

            try:
                collect_system_metrics()
            except Exception as e:
                print_log(
                    user=None,
                    level='warning',
                    message=f"Could not collect system metrics: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )

            try:
                latest = SystemMetrics.objects.order_by('-timestamp').first()
                if not latest:
                    print_log(
                        user=None,
                        level='error',
                        message="No SystemMetrics data available. Skipping resource check.",
                        exception_type='NoMetrics',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                # Check CPU if specified
                if max_cpu_percent is not None and latest.cpu_usage > max_cpu_percent:
                    print_log(
                        user=None,
                        level='error',
                        message=f"CPU usage too high: current {latest.cpu_usage:.1f}%, max allowed {max_cpu_percent}%. Skipping function.",
                        exception_type='HighCPUUsage',
                        file_path=func_file_path,
                        view_name=func.__name__
                    )
                    return

                # Check system memory if specified
                if min_memory is not None:
                    free_gb = latest.system_free_memory_gb
                    free_percent = latest.system_free_memory_percent
                    
                    if isinstance(min_memory, str) and min_memory.endswith('%'):
                        required_percent = float(min_memory.rstrip('%'))
                        if free_percent < required_percent:
                            print_log(
                                user=None,
                                level='error',
                                message=f"Not enough system memory: required {required_percent}%, available {free_percent:.2f}%. Skipping function.",
                                exception_type='InsufficientMemory',
                                file_path=func_file_path,
                                view_name=func.__name__
                            )
                            return
                    else:
                        required_gb = float(min_memory)
                        if free_gb < required_gb:
                            print_log(
                                user=None,
                                level='error',
                                message=f"Not enough system memory: required {required_gb} GB, available {free_gb:.2f} GB. Skipping function.",
                                exception_type='InsufficientMemory',
                                file_path=func_file_path,
                                view_name=func.__name__
                            )
                            return

                # Check GPU memory if specified
                if min_gpu_memory is not None:
                    if latest.gpu_total_memory_gb is None or latest.gpu_memory_usage is None:
                        print_log(
                            user=None,
                            level='error',
                            message="GPU check requested but no GPU detected. Skipping function.",
                            exception_type='NoGPUMetrics',
                            file_path=func_file_path,
                            view_name=func.__name__
                        )
                        return
                    
                    free_gb = latest.gpu_free_memory_gb
                    free_percent = latest.gpu_free_memory_percent
                    
                    if isinstance(min_gpu_memory, str) and min_gpu_memory.endswith('%'):
                        required_percent = float(min_gpu_memory.rstrip('%'))
                        if free_percent < required_percent:
                            print_log(
                                user=None,
                                level='error',
                                message=f"Not enough GPU memory: required {required_percent}%, available {free_percent:.2f}%. Skipping function.",
                                exception_type='InsufficientGPUMemory',
                                file_path=func_file_path,
                                view_name=func.__name__
                            )
                            return
                    else:
                        required_gb = float(min_gpu_memory)
                        if free_gb < required_gb:
                            print_log(
                                user=None,
                                level='error',
                                message=f"Not enough GPU memory: required {required_gb} GB, available {free_gb:.2f} GB. Skipping function.",
                                exception_type='InsufficientGPUMemory',
                                file_path=func_file_path,
                                view_name=func.__name__
                            )
                            return

            except Exception as e:
                print_log(
                    user=None,
                    level='error',
                    message=f"Resource check failed: {e}",
                    exception_type=type(e).__name__,
                    file_path=func_file_path,
                    view_name=func.__name__
                )
                return

            # All checks passed, run the function
            return func(*args, **kwargs)

        return wrapper
    return decorator


# Usage examples:
"""
@gpu_check('4.0')  # Requires 4GB free GPU memory
def train_model():
    pass

@gpu_check('30%')  # Requires 30% free GPU memory
def inference():
    pass

@memory_check('8.0')  # Requires 8GB free system RAM
def load_large_dataset():
    pass

@cpu_check(max_usage_percent=70)  # Only run if CPU usage is below 70%
def background_task():
    pass

@system_resources_check(min_memory='4.0', min_gpu_memory='2.0', max_cpu_percent=80)
def complex_operation():
    pass
"""