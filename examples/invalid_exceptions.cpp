#include <iostream>
#include <stdexcept>

void risk_throw(int val) {
    if (val < 0) {
        throw std::runtime_error("Value cannot be negative");
    }
}

int main() {
    try {
        risk_throw(-1);
    } catch (const std::exception& e) {
        std::cout << "Caught exception: " << e.what() << std::endl;
    }
    return 0;
}
