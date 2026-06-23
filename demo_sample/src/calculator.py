class Calculator:
    """
    Class Calculator thực hiện các phép toán cơ bản.
    """
    def __init__(self):
        pass

    def add(self, a: float, b: float) -> float:
        """
        Thực hiện phép tính cộng hai số.
        Ví dụ: add(1, 2) -> 3.0
        """
        # Gọi hàm logging helper để ghi nhận hoạt động
        self.log_operation("add", a, b)
        return float(a + b)

    def subtract(self, a: float, b: float) -> float:
        """
        Thực hiện phép tính trừ hai số.
        Ví dụ: subtract(5, 3) -> 2.0
        """
        self.log_operation("subtract", a, b)
        return float(a - b)

    def log_operation(self, operation: str, *args) -> None:
        """
        Hàm helper ghi lại log của phép toán.
        """
        print(f"Executing {operation} with arguments {args}")
