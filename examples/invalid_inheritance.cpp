#include <stdio.h>

class Base {
public:
    int value;
};

// 1. Virtual inheritance is forbidden
class VirtualDerived : virtual public Base {
public:
    int virtual_val;
};

class Actor {
public:
    float x, y;
};

class PhysicsObject {
public:
    float vx, vy;
    void ApplyForce(float fx, float fy) {
        vx += fx;
        vy += fy;
    }
};

// 2. Multiple inheritance of non-pure interfaces is forbidden
class PhysicsActor : public Actor, public PhysicsObject {
public:
    void Update() {
        x += vx;
        y += vy;
    }
};

int main() {
    PhysicsActor pa;
    pa.x = 0;
    pa.y = 0;
    pa.vx = 1.0f;
    pa.vy = 2.0f;
    pa.Update();
    printf("Position: (%f, %f)\n", pa.x, pa.y);
    return 0;
}
