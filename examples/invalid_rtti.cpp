#include <stdio.h>
#include <typeinfo>

class Base {
public:
    virtual ~Base() = default;
};

class Derived : public Base {
public:
    void derived_only_func() {
        printf("Derived function called\n");
    }
};

void check_type(Base* b) {
    // dynamic_cast requires RTTI and is forbidden in Orthodox C++
    Derived* d = dynamic_cast<Derived*>(b);
    if (d) {
        d->derived_only_func();
    }

    // typeid also requires RTTI and is forbidden
    const std::type_info& info = typeid(*b);
    printf("Type name: %s\n", info.name());
}

int main() {
    Derived d;
    check_type(&d);
    return 0;
}
