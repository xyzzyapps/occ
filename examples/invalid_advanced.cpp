#include <stdio.h>
#include <stdlib.h>

// 1. Macro definition (Preprocessor violation)
#define MAX_VALUE 100

// 2. Template definition (Template violation)
template <typename T>
class Box {
public:
    T value;

    // 3. Single-argument constructor without 'explicit' (Explicit violation)
    Box(T val) : value(val) {}

    // 4. Custom operator overloading (Operator violation)
    Box operator+(const Box& other) {
        return Box(value + other.value);
    }
};

int main() {
    // 1. Macro expansion (Preprocessor violation)
    int limit = MAX_VALUE;
    printf("Limit: %d\n", limit);

    // 2. Template instantiation/type usage (Template violation)
    Box<int> box1(10);
    Box<int> box2(20);
    Box<int> box3 = box1 + box2;

    // 5. C++ heap allocation/deallocation (Heap violation)
    int* ptr1 = new int(5);
    delete ptr1;

    // 5. C library heap allocation/deallocation (Heap violation)
    int* ptr2 = (int*)malloc(sizeof(int));
    free(ptr2);

    // 6. Lambda expression (Lambda violation)
    auto my_lambda = [](int x) {
        return x * x;
    };
    printf("Lambda result: %d\n", my_lambda(5));

    return 0;
}
