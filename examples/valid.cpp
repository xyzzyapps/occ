#include <stdio.h>

// A clean base class
class Entity {
public:
    int id;
    float x, y;

    Entity(int entity_id) : id(entity_id), x(0.0f), y(0.0f) {}
    
    // Virtual methods are allowed, but not virtual inheritance
    virtual void Update(float dt) {
        x += dt;
        y += dt;
    }
};

// Single inheritance is allowed
class Player : public Entity {
public:
    int score;

    Player(int id) : Entity(id), score(0) {}

    void Update(float dt) override {
        Entity::Update(dt);
        score += 1;
    }
};

// Pure interfaces for multiple inheritance
class IRenderable {
public:
    virtual ~IRenderable() = default;
    virtual void Draw() = 0;
};

class ISerializable {
public:
    virtual ~ISerializable() = default;
    virtual void Serialize(char* buffer) = 0;
};

// Inheriting from multiple interfaces is allowed
class SpritePlayer : public Player, public IRenderable, public ISerializable {
public:
    SpritePlayer(int id) : Player(id) {}

    void Draw() override {
        printf("Drawing player %d at (%f, %f)\n", id, x, y);
    }

    void Serialize(char* buffer) override {
        sprintf(buffer, "Player %d: score %d", id, score);
    }
};

int main() {
    SpritePlayer player(1);
    player.Update(0.16f);
    player.Draw();
    return 0;
}
