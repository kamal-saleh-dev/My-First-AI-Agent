# unreal_templates.py — Unreal Engine C++ validation, fixes, and prompts
# Edit here without touching agent.py
import re

def validate_unreal(code):
    required = ["#include", "GENERATED_BODY"]
    for r in required:
        if r.lower() not in code.lower():
            return False, f"Missing Unreal requirement: {r}"

    if ".generated.h" not in code:
        return False, "Missing .generated.h include"

    # regex صح عشان مينفعش يعتبر UActorComponent كـ UComponent أو UObject
    if re.search(r'public\s+UComponent\b', code):
        return False, "Invalid Unreal inheritance: Use UActorComponent instead of UComponent"

    if re.search(r'public\s+UObject\b', code):
        return False, "Component must inherit from UActorComponent, not UObject"

    return True, "Valid Unreal Header"

def auto_fix_unreal_header(header_code):
    """
    Inject missing .generated.h include if absent.
    """
    if ".generated.h" in header_code:
        return header_code, False

    # Extract class name
    class_match = re.search(
        r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        header_code
    )

    if not class_match:
        return header_code, False

    class_name = class_match.group(1)

    include_line = f'#include "{class_name}.generated.h"\n'

    # نحاول نحطه بعد آخر include
    includes = list(re.finditer(r'#include\s+["<].*[">]', header_code))
    if includes:
        last_include = includes[-1]
        insert_pos = last_include.end()
        fixed_header = (
            header_code[:insert_pos]
            + "\n"
            + include_line
            + header_code[insert_pos:]
        )
    else:
        # لو مفيش includes خالص
        fixed_header = include_line + header_code

    return fixed_header, True

UNREAL_SYSTEM_PROMPT = """You are a senior Unreal Engine C++ developer.

STRICT OUTPUT RULES:
1) Return EXACTLY TWO ```cpp blocks. Nothing else outside them.
2) First block = Header (.h), Second block = CPP (.cpp)
3) Header MUST:
   - Start with #pragma once
   - #include "CoreMinimal.h"
   - #include "Components/ActorComponent.h"
   - #include "<ExactClassName>.generated.h"
   - UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
   - class MYGAME_API <ClassName> : public UActorComponent
   - GENERATED_BODY()
   - Declare constructor, ALL functions, UPROPERTY, UFUNCTION, delegates
4) CPP MUST:
   - #include "<ExactClassName>.h" (SAME name as the class file)
   - Implement constructor and ALL declared functions
5) NO text or explanations outside the two code blocks.

EXAMPLE:
```cpp
#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MyComp.generated.h"

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UMyComp : public UActorComponent
{
    GENERATED_BODY()
public:
    UMyComp();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float Value;
    UFUNCTION(BlueprintCallable)
    void DoSomething(float Amount);
protected:
    virtual void BeginPlay() override;
};
```
```cpp
#include "MyComp.h"

UMyComp::UMyComp()
{
    PrimaryComponentTick.bCanEverTick = false;
}
void UMyComp::BeginPlay()
{
    Super::BeginPlay();
}
void UMyComp::DoSomething(float Amount)
{
    Value -= Amount;
}
```"""


# ══════════════════════════════════════════════════════════════
# UNREAL GAME TYPE TEMPLATES
# ══════════════════════════════════════════════════════════════

UNREAL_GAME_TEMPLATES = {

    "shooter_player": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "ShooterCharacter.generated.h"

UCLASS()
class MYGAME_API AShooterCharacter : public ACharacter
{{
    GENERATED_BODY()
public:
    AShooterCharacter();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float MoveSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    int32 MaxHealth = 100;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat")
    int32 CurrentHealth;
    UFUNCTION(BlueprintCallable) void Shoot();
    UFUNCTION(BlueprintCallable) void TakeDamage(int32 Damage);
protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(class UInputComponent* PI) override;
private:
    void MoveForward(float Value);
    void MoveRight(float Value);
    UPROPERTY(EditAnywhere) TSubclassOf<class AActor> ProjectileClass;
};""",

    "rpg_character": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "RPGCharacter.generated.h"

UENUM(BlueprintType)
enum class ECharacterClass : uint8 {{ Warrior, Mage, Archer, Rogue }};

UCLASS()
class MYGAME_API ARPGCharacter : public ACharacter
{{
    GENERATED_BODY()
public:
    ARPGCharacter();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="RPG")
    ECharacterClass CharacterClass = ECharacterClass::Warrior;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 Level = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 Experience = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 MaxHealth = 100;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats")
    int32 CurrentHealth;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float AttackDamage = 20.f;
    UFUNCTION(BlueprintCallable) void GainExperience(int32 Amount);
    UFUNCTION(BlueprintCallable) void LevelUp();
    UFUNCTION(BlueprintCallable) void Attack(AActor* Target);
    UFUNCTION(BlueprintCallable) void TakeDamage(int32 Damage);
protected:
    virtual void BeginPlay() override;
    int32 ExperienceToNextLevel() const;
};""",

    "enemy_ai": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "EnemyCharacter.generated.h"

UENUM(BlueprintType)
enum class EEnemyState : uint8 {{ Idle, Patrol, Chase, Attack, Dead }};

UCLASS()
class MYGAME_API AEnemyCharacter : public ACharacter
{{
    GENERATED_BODY()
public:
    AEnemyCharacter();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI")
    float DetectionRadius = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI")
    float AttackRange = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 MaxHealth = 50;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats")
    int32 CurrentHealth;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 AttackDamage = 10;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="AI")
    EEnemyState CurrentState = EEnemyState::Idle;
    UFUNCTION(BlueprintCallable) void TakeDamage(int32 Damage);
    UFUNCTION(BlueprintCallable) void SetTarget(AActor* NewTarget);
protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
private:
    AActor* Target;
    void UpdateAI(float DeltaTime);
    void Die();
};""",

    "health_component": """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "HealthComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnHealthChanged, float, NewHealth, float, MaxHealth);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDeath);

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UHealthComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UHealthComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health")
    float MaxHealth = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Health")
    float CurrentHealth;
    UPROPERTY(BlueprintAssignable) FOnHealthChanged OnHealthChanged;
    UPROPERTY(BlueprintAssignable) FOnDeath OnDeath;
    UFUNCTION(BlueprintCallable) void TakeDamage(float Damage);
    UFUNCTION(BlueprintCallable) void Heal(float Amount);
    UFUNCTION(BlueprintPure) float GetHealthPercent() const;
    UFUNCTION(BlueprintPure) bool IsAlive() const;
protected:
    virtual void BeginPlay() override;
};""",

    "game_mode": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "MyGameMode.generated.h"

UCLASS()
class MYGAME_API AMyGameMode : public AGameModeBase
{{
    GENERATED_BODY()
public:
    AMyGameMode();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Game")
    int32 ScorePerKill = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Game")
    int32 Lives = 3;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Game")
    int32 CurrentScore = 0;
    UFUNCTION(BlueprintCallable) void AddScore(int32 Amount);
    UFUNCTION(BlueprintCallable) void OnEnemyKilled();
    UFUNCTION(BlueprintCallable) void OnPlayerDied();
    UFUNCTION(BlueprintCallable) void GameOver();
    UFUNCTION(BlueprintCallable) void Win();
protected:
    virtual void BeginPlay() override;
};""",

    "weapon": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Weapon.generated.h"

UENUM(BlueprintType)
enum class EWeaponType : uint8 {{ Pistol, Rifle, Shotgun, Sniper, Melee }};

UCLASS()
class MYGAME_API AWeapon : public AActor
{{
    GENERATED_BODY()
public:
    AWeapon();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weapon")
    EWeaponType WeaponType = EWeaponType::Pistol;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 Damage = 25;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    int32 MaxAmmo = 30;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats")
    int32 CurrentAmmo;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float FireRate = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float ReloadTime = 2.f;
    UFUNCTION(BlueprintCallable) void Fire();
    UFUNCTION(BlueprintCallable) void Reload();
    UFUNCTION(BlueprintPure) bool CanFire() const;
protected:
    virtual void BeginPlay() override;
private:
    float LastFireTime = 0.f;
    bool bIsReloading = false;
};""",

    "inventory": """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InventoryComponent.generated.h"

USTRUCT(BlueprintType)
struct FInventoryItem
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Name;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Quantity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxStack = 99;
}};

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UInventoryComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UInventoryComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Inventory")
    int32 MaxSlots = 20;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Inventory")
    TArray<FInventoryItem> Items;
    UFUNCTION(BlueprintCallable) bool AddItem(FInventoryItem Item);
    UFUNCTION(BlueprintCallable) bool RemoveItem(FString ItemName, int32 Amount = 1);
    UFUNCTION(BlueprintCallable) bool HasItem(FString ItemName, int32 Amount = 1) const;
    UFUNCTION(BlueprintCallable) int32 GetItemCount(FString ItemName) const;
protected:
    virtual void BeginPlay() override;
};""",

    "quest": """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "QuestComponent.generated.h"

UENUM(BlueprintType)
enum class EQuestStatus : uint8 {{ Available, Active, Completed, Failed }};

USTRUCT(BlueprintType)
struct FQuest
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString QuestName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 RequiredKills = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 CurrentKills  = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 RewardScore   = 500;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EQuestStatus Status = EQuestStatus::Available;
}};

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UQuestComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UQuestComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Quests")
    TArray<FQuest> Quests;
    UFUNCTION(BlueprintCallable) void StartQuest(int32 Index);
    UFUNCTION(BlueprintCallable) void UpdateKillProgress(int32 Index, int32 Amount = 1);
    UFUNCTION(BlueprintCallable) bool IsQuestComplete(int32 Index) const;
protected:
    virtual void BeginPlay() override;
};""",

    "save_system": """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "MySaveGame.generated.h"

UCLASS()
class MYGAME_API UMySaveGame : public USaveGame
{{
    GENERATED_BODY()
public:
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save")
    int32 SavedScore = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save")
    int32 SavedLevel = 1;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save")
    FVector SavedPosition = FVector::ZeroVector;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save")
    TArray<FString> UnlockedAbilities;
    static void Save(UMySaveGame* Data, FString SlotName = "Save1");
    static UMySaveGame* Load(FString SlotName = "Save1");
};""",

    "wave_spawner": """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WaveSpawner.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaveComplete, int32, WaveNumber);

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UWaveSpawner : public UActorComponent
{{
    GENERATED_BODY()
public:
    UWaveSpawner();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves")
    TArray<TSubclassOf<AActor>> EnemyTypes;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves")
    TArray<AActor*> SpawnPoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves")
    int32 EnemiesPerWave = 5;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves")
    float TimeBetweenWaves = 5.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Waves")
    int32 CurrentWave = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Waves")
    int32 EnemiesAlive = 0;
    UPROPERTY(BlueprintAssignable) FOnWaveComplete OnWaveComplete;
    UFUNCTION(BlueprintCallable) void StartWaves();
    UFUNCTION(BlueprintCallable) void OnEnemyKilled();
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle WaveTimer;
    void SpawnWave();
};""",
}

# Keywords for Unreal game types
UNREAL_GAME_KEYWORDS = {
    "shooter_player": ["shooter","fps","tps","third person","first person","gunner"],
    "rpg_character":  ["rpg","adventure","quest","hero","dungeon","fantasy"],
    "enemy_ai":       ["enemy","ai","monster","npc enemy","creature","foe"],
    "health_component":["health","hp","damage","heal","death","life"],
    "game_mode":      ["game mode","gamemode","score","lives","manager","gm"],
    "weapon":         ["weapon","gun","rifle","pistol","shotgun","sword","firearm"],
    "inventory":      ["inventory","items","loot","bag","equip","pickup"],
    "quest":          ["quest","mission","task","objective","storyline"],
    "save_system":    ["save","load","persist","checkpoint","data","save game"],
    "wave_spawner":   ["wave","spawn","spawner","enemy wave","horde"],
}




# ── Additional Unreal Templates ──────────────────────────────────

UNREAL_GAME_TEMPLATES["save_system"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "MySaveGame.generated.h"
UCLASS()
class MYGAME_API UMySaveGame : public USaveGame
{{
    GENERATED_BODY()
public:
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save") int32 SavedScore = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save") int32 SavedLevel = 1;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save") FVector SavedPosition = FVector::ZeroVector;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save") float SavedHealth = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category="Save") TArray<FString> UnlockedAbilities;
    UFUNCTION(BlueprintCallable, Category="Save") static void SaveGame(UMySaveGame* Data, const FString& SlotName = "Slot1");
    UFUNCTION(BlueprintCallable, Category="Save") static UMySaveGame* LoadGame(const FString& SlotName = "Slot1");
    UFUNCTION(BlueprintCallable, Category="Save") static bool HasSave(const FString& SlotName = "Slot1");
};"""

UNREAL_GAME_TEMPLATES["dialogue"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DialogueComponent.generated.h"
USTRUCT(BlueprintType)
struct FDialogueLine
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Speaker;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(MultiLine=true)) FText Text;
}};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnDialogueLine, FString, Speaker, FText, Text);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDialogueEnd);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UDialogueComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UDialogueComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dialogue") TArray<FDialogueLine> Lines;
    UPROPERTY(BlueprintAssignable) FOnDialogueLine OnDialogueLine;
    UPROPERTY(BlueprintAssignable) FOnDialogueEnd OnDialogueEnd;
    UFUNCTION(BlueprintCallable) void StartDialogue();
    UFUNCTION(BlueprintCallable) void NextLine();
    UFUNCTION(BlueprintPure) bool IsActive() const;
protected:
    virtual void BeginPlay() override;
private:
    int32 CurrentIndex = 0;
    bool bIsActive = false;
};"""

UNREAL_GAME_TEMPLATES["game_instance"] = """#pragma once
#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "MyGameInstance.generated.h"
UCLASS()
class MYGAME_API UMyGameInstance : public UGameInstance
{{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadWrite, Category="Game") int32 TotalScore = 0;
    UPROPERTY(BlueprintReadWrite, Category="Game") int32 CurrentLevel = 1;
    UPROPERTY(BlueprintReadWrite, Category="Game") FString PlayerName = "Player";
    UPROPERTY(BlueprintReadWrite, Category="Game") TArray<FString> UnlockedLevels;
    UFUNCTION(BlueprintCallable) void AddScore(int32 Amount);
    UFUNCTION(BlueprintCallable) void NextLevel();
    UFUNCTION(BlueprintCallable) void SaveProgress();
    UFUNCTION(BlueprintCallable) void LoadProgress();
    virtual void Init() override;
};"""

UNREAL_GAME_TEMPLATES["character_movement"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CustomMovement.generated.h"
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCustomMovement : public UActorComponent
{{
    GENERATED_BODY()
public:
    UCustomMovement();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float WalkSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float SprintSpeed = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float CrouchSpeed = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Jump")     float JumpForce = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Jump")     int32 MaxJumps = 2;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)                    int32 JumpsLeft;
    UFUNCTION(BlueprintCallable) void Sprint(bool bSprint);
    UFUNCTION(BlueprintCallable) void Crouch(bool bCrouch);
    UFUNCTION(BlueprintCallable) void Jump();
    UFUNCTION(BlueprintCallable) void OnLanded();
    UFUNCTION(BlueprintPure)     bool IsSprinting() const;
    UFUNCTION(BlueprintPure)     bool IsCrouching() const;
protected:
    virtual void BeginPlay() override;
private:
    bool bIsSprinting = false;
    bool bIsCrouching = false;
    class UCharacterMovementComponent* MovComp;
};"""

UNREAL_GAME_TEMPLATES["ui_hud"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Blueprint/UserWidget.h"
#include "MyHUD.generated.h"
UCLASS()
class MYGAME_API AMyHUD : public AHUD
{{
    GENERATED_BODY()
public:
    AMyHUD();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="HUD") TSubclassOf<UUserWidget> HealthBarClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="HUD") TSubclassOf<UUserWidget> AmmoDisplayClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="HUD") TSubclassOf<UUserWidget> ScoreDisplayClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="HUD") TSubclassOf<UUserWidget> GameOverScreenClass;
    UFUNCTION(BlueprintCallable) void ShowHUD();
    UFUNCTION(BlueprintCallable) void HideHUD();
    UFUNCTION(BlueprintCallable) void ShowGameOver();
    UFUNCTION(BlueprintCallable) void UpdateHealth(float Percent);
    UFUNCTION(BlueprintCallable) void UpdateAmmo(int32 Current, int32 Max);
    UFUNCTION(BlueprintCallable) void UpdateScore(int32 Score);
protected:
    virtual void BeginPlay() override;
private:
    UPROPERTY() UUserWidget* HealthBarWidget;
    UPROPERTY() UUserWidget* HUDWidget;
};"""

UNREAL_GAME_TEMPLATES["projectile"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "Components/SphereComponent.h"
#include "AProjectile.generated.h"
UCLASS()
class MYGAME_API AProjectile : public AActor
{{
    GENERATED_BODY()
public:
    AProjectile();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") int32 Damage = 25;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float Lifetime = 3.f;
    UPROPERTY(VisibleAnywhere) USphereComponent* CollisionComp;
    UPROPERTY(VisibleAnywhere) UProjectileMovementComponent* ProjectileMovement;
    UFUNCTION(BlueprintCallable) void SetDamage(int32 NewDamage);
protected:
    virtual void BeginPlay() override;
private:
    UFUNCTION() void OnHit(UPrimitiveComponent* HitComp, AActor* OtherActor,
                           UPrimitiveComponent* OtherComp, FVector NormalImpulse,
                           const FHitResult& Hit);
};"""

UNREAL_GAME_TEMPLATES["audio_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Sound/SoundCue.h"
#include "AudioManagerComponent.generated.h"
USTRUCT(BlueprintType)
struct FSoundEntry
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Name;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) USoundCue* Sound;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Volume = 1.f;
}};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAudioManagerComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UAudioManagerComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Audio") TArray<FSoundEntry> Sounds;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Audio") float MasterVolume = 1.f;
    UFUNCTION(BlueprintCallable) void PlaySound(const FString& Name);
    UFUNCTION(BlueprintCallable) void StopSound(const FString& Name);
    UFUNCTION(BlueprintCallable) void SetMasterVolume(float Volume);
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["npc_ai"] = """#pragma once
#include "CoreMinimal.h"
#include "AIController.h"
#include "BehaviorTree/BehaviorTree.h"
#include "NPC_AIController.generated.h"
UCLASS()
class MYGAME_API ANPC_AIController : public AAIController
{{
    GENERATED_BODY()
public:
    ANPC_AIController();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") UBehaviorTree* BehaviorTree;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float PatrolRadius = 500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float SightRadius  = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float HearingRadius = 400.f;
    UFUNCTION(BlueprintCallable) void SetTarget(AActor* NewTarget);
    UFUNCTION(BlueprintCallable) void AlertNearby(float Radius);
    UFUNCTION(BlueprintPure)     AActor* GetTarget() const;
protected:
    virtual void BeginPlay() override;
    virtual void OnPossess(APawn* InPawn) override;
private:
    AActor* CurrentTarget;
};"""

UNREAL_GAME_TEMPLATES["interactable"] = """#pragma once
#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "Interactable.generated.h"
UINTERFACE(MinimalAPI, BlueprintType)
class UInteractable : public UInterface {{ GENERATED_BODY() }};
class MYGAME_API IInteractable
{{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, BlueprintNativeEvent) void Interact(AActor* Interactor);
    UFUNCTION(BlueprintCallable, BlueprintNativeEvent) FText GetInteractPrompt();
    UFUNCTION(BlueprintCallable, BlueprintNativeEvent) bool CanInteract(AActor* Interactor);
}};

// ─── Example pickup implementing IInteractable ───────────────────
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Interactable.h"
#include "PickupActor.generated.h"
UCLASS()
class MYGAME_API APickupActor : public AActor, public IInteractable
{{
    GENERATED_BODY()
public:
    APickupActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") FString ItemName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") int32 Amount = 1;
    virtual void Interact_Implementation(AActor* Interactor) override;
    virtual FText GetInteractPrompt_Implementation() override;
    virtual bool CanInteract_Implementation(AActor* Interactor) override;
};"""

UNREAL_GAME_TEMPLATES["object_pool"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ObjectPoolComponent.generated.h"
USTRUCT(BlueprintType)
struct FObjectPool
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<AActor> ActorClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 PoolSize = 20;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString PoolTag;
    TArray<AActor*> PooledActors;
}};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UObjectPoolComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UObjectPoolComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pool") TArray<FObjectPool> Pools;
    UFUNCTION(BlueprintCallable) AActor* Spawn(const FString& Tag, FVector Location, FRotator Rotation);
    UFUNCTION(BlueprintCallable) void ReturnToPool(AActor* Actor, const FString& Tag);
    UFUNCTION(BlueprintCallable) void InitializePools();
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["ability_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AbilityComponent.generated.h"
UENUM(BlueprintType)
enum class EAbilityType : uint8 {{ Dash, Shield, Heal, AOE, Teleport, TimeStop }};
USTRUCT(BlueprintType)
struct FAbility
{{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EAbilityType Type;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Cooldown = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float ManaCost = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bUnlocked = false;
    float LastUsedTime = -999.f;
}};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAbilityComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UAbilityComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Abilities") TArray<FAbility> Abilities;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float MaxMana = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats") float CurrentMana;
    UFUNCTION(BlueprintCallable) bool UseAbility(int32 Index);
    UFUNCTION(BlueprintCallable) void UnlockAbility(int32 Index);
    UFUNCTION(BlueprintCallable) float GetCooldownRemaining(int32 Index) const;
    UFUNCTION(BlueprintCallable) void RegenerateMana(float Amount);
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["minimap"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/ActorComponent.h"
#include "MinimapComponent.generated.h"
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UMinimapComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UMinimapComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Minimap") float CaptureHeight = 2000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Minimap") float CaptureRadius = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Minimap") UTextureRenderTarget2D* RenderTarget;
    UFUNCTION(BlueprintCallable) void InitializeMinimap(AActor* TrackedActor);
    UFUNCTION(BlueprintCallable) void UpdateMinimap();
    UFUNCTION(BlueprintCallable) void AddMarker(FVector WorldPos, FLinearColor Color);
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
private:
    USceneCaptureComponent2D* CaptureComp;
    AActor* TargetActor;
};"""

UNREAL_GAME_TEMPLATES["day_night"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/DirectionalLight.h"
#include "DayNightComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTimeChanged, float, TimeOfDay);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UDayNightComponent : public UActorComponent
{{
    GENERATED_BODY()
public:
    UDayNightComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Time") float DayDuration = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Time") float StartTime = 0.25f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Time") float CurrentTime;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Light") ADirectionalLight* Sun;
    UPROPERTY(BlueprintAssignable) FOnTimeChanged OnTimeChanged;
    UFUNCTION(BlueprintPure) bool IsDay() const;
    UFUNCTION(BlueprintPure) bool IsNight() const;
    UFUNCTION(BlueprintPure) float GetHour() const;
    UFUNCTION(BlueprintCallable) void SetTime(float NormalizedTime);
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
};"""

# Update Unreal keywords
UNREAL_GAME_KEYWORDS.update({
    "save_system":         ["save","load","persist","save game","checkpoint data"],
    "dialogue":            ["dialogue","dialog","conversation","talk","npc talk","cutscene"],
    "game_instance":       ["game instance","persistent","global data","cross level"],
    "character_movement":  ["movement","sprint","crouch","double jump","parkour","movement comp"],
    "ui_hud":              ["hud","ui","widget","health bar","ammo display","score display"],
    "projectile":          ["projectile","bullet","rocket","missile","arrow","shot"],
    "audio_manager":       ["audio","sound","music","sfx","mixer","audio manager"],
    "npc_ai":              ["npc ai","patrol","behavior tree","ai controller","npc"],
    "interactable":        ["interact","pickup","use","press e","interactable","interface"],
    "object_pool":         ["pool","object pool","bullet pool","pooling","performance"],
    "ability_system":      ["ability","dash","shield","skill","active skill","power"],
    "minimap":             ["minimap","radar","map","scene capture","overhead"],
    "day_night":           ["day","night","cycle","sun","time of day","24 hour"],
})

def get_unreal_template(name: str, role: str = None) -> str:
    """Get Unreal header template by name or role."""
    nl = name.lower()
    for key, keywords in UNREAL_GAME_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return UNREAL_GAME_TEMPLATES.get(key, "")
    if role and role in UNREAL_GAME_TEMPLATES:
        return UNREAL_GAME_TEMPLATES[role]
    return ""


UNREAL_GAME_TEMPLATES["shooter_character"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "ShooterCharacter.generated.h"
UCLASS()
class MYGAME_API AShooterCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    AShooterCharacter();
    UPROPERTY(VisibleAnywhere) USpringArmComponent* SpringArm;
    UPROPERTY(VisibleAnywhere) UCameraComponent*    Camera;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") int32 MaxHealth = 100;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats") int32 CurrentHealth;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") float FireRate = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") TSubclassOf<class AProjectile> ProjectileClass;
    UFUNCTION(BlueprintCallable) void Fire();
    UFUNCTION(BlueprintCallable) void TakeDamage(int32 Damage);
    UFUNCTION(BlueprintCallable) void Reload();
    UFUNCTION(BlueprintCallable) void AimDownSights(bool bAiming);
protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(class UInputComponent* PI) override;
    virtual void Tick(float DeltaTime) override;
private:
    float LastFireTime = 0.f;
    bool bIsAiming = false;
    void MoveForward(float Value);
    void MoveRight(float Value);
    void LookUp(float Value);
    void Turn(float Value);
};"""

UNREAL_GAME_TEMPLATES["rpg_stats"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "RPGStatsComponent.generated.h"
UENUM(BlueprintType)
enum class EStat : uint8 { Strength, Dexterity, Intelligence, Endurance, Charisma };
USTRUCT(BlueprintType)
struct FStatBlock
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Strength    = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Dexterity   = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Intelligence= 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Endurance   = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Charisma    = 10;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnLevelUp, int32, OldLevel, int32, NewLevel);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API URPGStatsComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    URPGStatsComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="RPG") FStatBlock Stats;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="RPG") int32 Level = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="RPG") int32 Experience = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="RPG") int32 StatPoints = 0;
    UPROPERTY(BlueprintAssignable) FOnLevelUp OnLevelUp;
    UFUNCTION(BlueprintCallable) void GainExperience(int32 Amount);
    UFUNCTION(BlueprintCallable) void UpgradeStat(EStat Stat, int32 Amount = 1);
    UFUNCTION(BlueprintPure) int32 GetAttackDamage() const;
    UFUNCTION(BlueprintPure) float GetMoveSpeedMultiplier() const;
    UFUNCTION(BlueprintPure) int32 ExperienceNeeded() const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["loot_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LootComponent.generated.h"
UENUM(BlueprintType)
enum class EItemRarity : uint8 { Common, Uncommon, Rare, Epic, Legendary };
USTRUCT(BlueprintType)
struct FLootItem
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ItemName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EItemRarity Rarity = EItemRarity::Common;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Quantity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="0",ClampMax="100")) float DropChance = 50.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<AActor> PickupClass;
};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API ULootComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    ULootComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Loot") TArray<FLootItem> LootTable;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Loot") float RarityMultiplier = 1.f;
    UFUNCTION(BlueprintCallable) TArray<FLootItem> RollLoot();
    UFUNCTION(BlueprintCallable) void SpawnLootAtLocation(FVector Location);
    UFUNCTION(BlueprintPure) float GetRarityChance(EItemRarity Rarity) const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["crafting_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CraftingComponent.generated.h"
USTRUCT(BlueprintType)
struct FCraftingIngredient
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ItemName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Quantity = 1;
};
USTRUCT(BlueprintType)
struct FCraftingRecipe
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ResultItem;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 ResultQuantity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FCraftingIngredient> Ingredients;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float CraftTime = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bRequiresCraftingTable = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCraftComplete, FString, ItemName);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCraftingComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCraftingComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Crafting") TArray<FCraftingRecipe> Recipes;
    UPROPERTY(BlueprintAssignable) FOnCraftComplete OnCraftComplete;
    UFUNCTION(BlueprintCallable) bool CanCraft(int32 RecipeIndex, UActorComponent* Inventory) const;
    UFUNCTION(BlueprintCallable) void StartCrafting(int32 RecipeIndex, UActorComponent* Inventory);
    UFUNCTION(BlueprintCallable) void CancelCrafting();
    UFUNCTION(BlueprintPure) TArray<FCraftingRecipe> GetAvailableRecipes(UActorComponent* Inventory) const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle CraftTimer;
    int32 CurrentRecipeIndex = -1;
};"""

UNREAL_GAME_TEMPLATES["stamina_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StaminaComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStaminaDepleted);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStaminaFull);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UStaminaComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UStaminaComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stamina") float MaxStamina = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stamina") float CurrentStamina;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stamina") float SprintCost   = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stamina") float AttackCost   = 15.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stamina") float RegenRate    = 10.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stamina") float RegenDelay   = 1.5f;
    UPROPERTY(BlueprintAssignable) FOnStaminaDepleted OnStaminaDepleted;
    UPROPERTY(BlueprintAssignable) FOnStaminaFull     OnStaminaFull;
    UFUNCTION(BlueprintCallable) bool UseStamina(float Amount);
    UFUNCTION(BlueprintCallable) void RegainStamina(float Amount);
    UFUNCTION(BlueprintPure) float GetStaminaPercent() const;
    UFUNCTION(BlueprintPure) bool HasEnoughStamina(float Amount) const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
private:
    float TimeSinceLastUse = 0.f;
    bool bIsRegenerating = false;
};"""

UNREAL_GAME_TEMPLATES["stealth_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StealthComponent.generated.h"
UENUM(BlueprintType)
enum class EStealthState : uint8 { Hidden, Suspicious, Detected };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnStealthStateChanged, EStealthState, NewState);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UStealthComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UStealthComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stealth") float NoiseRadius      = 200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stealth") float CrouchNoiseMultiplier = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stealth") float LightThreshold   = 0.3f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stealth") float CurrentVisibility = 0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stealth") EStealthState StealthState;
    UPROPERTY(BlueprintAssignable) FOnStealthStateChanged OnStealthStateChanged;
    UFUNCTION(BlueprintCallable) void UpdateVisibility(float LightLevel, bool bIsCrouching, float Speed);
    UFUNCTION(BlueprintCallable) void MakeNoise(float Volume);
    UFUNCTION(BlueprintCallable) void Hide();
    UFUNCTION(BlueprintPure) bool IsHidden() const;
    UFUNCTION(BlueprintPure) float GetNoiseMade(float Speed, bool bCrouch) const;
protected:
    virtual void BeginPlay() override;
private:
    void SetStealthState(EStealthState NewState);
};"""

UNREAL_GAME_TEMPLATES["vehicle_component"] = """#pragma once
#include "CoreMinimal.h"
#include "WheeledVehiclePawn.h"
#include "VehicleCharacter.generated.h"
UCLASS()
class MYGAME_API AVehicleCharacter : public AWheeledVehiclePawn
{
    GENERATED_BODY()
public:
    AVehicleCharacter();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle") float MaxSpeed      = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle") float BoostForce    = 5000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle") float BoostDuration = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle") int32 MaxHealth     = 200;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Vehicle") int32 CurrentHealth;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Vehicle") bool bIsBoosting = false;
    UFUNCTION(BlueprintCallable) void ActivateBoost();
    UFUNCTION(BlueprintCallable) void TakeDamage(int32 Damage);
    UFUNCTION(BlueprintCallable) void Repair(int32 Amount);
    UFUNCTION(BlueprintPure) float GetSpeedKMH() const;
protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(class UInputComponent* PI) override;
private:
    FTimerHandle BoostTimer;
    void Throttle(float Value);
    void Steer(float Value);
    void Brake(float Value);
    void DeactivateBoost();
};"""

UNREAL_GAME_TEMPLATES["network_component"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Net/UnrealNetwork.h"
#include "NetworkComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnNetworkEvent, FString, EventName, FString, Data);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UNetworkComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UNetworkComponent();
    UPROPERTY(ReplicatedUsing=OnRep_Health, BlueprintReadOnly, Category="Network") int32 ReplicatedHealth = 100;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Network") int32 ReplicatedScore = 0;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Network") FString PlayerName;
    UPROPERTY(BlueprintAssignable) FOnNetworkEvent OnNetworkEvent;
    UFUNCTION(BlueprintCallable, Server, Reliable) void ServerTakeDamage(int32 Damage);
    UFUNCTION(BlueprintCallable, Server, Reliable) void ServerAddScore(int32 Amount);
    UFUNCTION(NetMulticast, Reliable) void MulticastPlayEffect(FString EffectName);
    UFUNCTION(BlueprintPure) bool IsLocallyControlled() const;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Props) const override;
protected:
    virtual void BeginPlay() override;
    UFUNCTION() void OnRep_Health();
};"""

UNREAL_GAME_TEMPLATES["procedural_dungeon"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProceduralDungeonComponent.generated.h"
UENUM(BlueprintType)
enum class ERoomType : uint8 { Normal, Boss, Treasure, Shop, Start, Exit };
USTRUCT(BlueprintType)
struct FDungeonRoom
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FIntPoint GridPos;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FIntPoint Size = FIntPoint(10,10);
    UPROPERTY(EditAnywhere, BlueprintReadWrite) ERoomType RoomType = ERoomType::Normal;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FIntPoint> ConnectedRooms;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bCleared = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDungeonGenerated, int32, RoomCount);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UProceduralDungeonComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProceduralDungeonComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dungeon") int32 RoomCount        = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dungeon") int32 GridSize         = 20;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dungeon") float BossRoomChance   = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dungeon") float TreasureChance   = 0.15f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Dungeon") TArray<FDungeonRoom> Rooms;
    UPROPERTY(BlueprintAssignable) FOnDungeonGenerated OnDungeonGenerated;
    UFUNCTION(BlueprintCallable) void GenerateDungeon(int32 Seed = -1);
    UFUNCTION(BlueprintCallable) void ClearRoom(int32 RoomIndex);
    UFUNCTION(BlueprintPure) FDungeonRoom GetCurrentRoom(FVector PlayerPos) const;
    UFUNCTION(BlueprintPure) bool AreAllRoomsCleared() const;
protected:
    virtual void BeginPlay() override;
private:
    void PlaceRooms(int32 Seed);
    void ConnectRooms();
    void AssignRoomTypes();
};"""

UNREAL_GAME_TEMPLATES["boss_fight"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BossCharacter.generated.h"
UENUM(BlueprintType)
enum class EBossPhase : uint8 { Phase1, Phase2, Phase3, Enraged, Dead };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBossPhaseChange, EBossPhase, NewPhase);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnBossDefeated);
UCLASS()
class MYGAME_API ABossCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    ABossCharacter();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") FString BossName = "Boss";
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") float MaxHealth    = 5000.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Boss") float CurrentHealth;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Boss") EBossPhase CurrentPhase = EBossPhase::Phase1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") float Phase2Threshold = 0.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") float Phase3Threshold = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") float AttackDamage   = 40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss") TArray<TSubclassOf<AActor>> AttackAbilities;
    UPROPERTY(BlueprintAssignable) FOnBossPhaseChange OnBossPhaseChange;
    UPROPERTY(BlueprintAssignable) FOnBossDefeated   OnBossDefeated;
    UFUNCTION(BlueprintCallable) void TakeDamage(float Damage);
    UFUNCTION(BlueprintCallable) void UseRandomAbility();
    UFUNCTION(BlueprintCallable) void EnterPhase(EBossPhase Phase);
    UFUNCTION(BlueprintPure) float GetHealthPercent() const;
protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
private:
    void CheckPhaseTransition();
    void Die();
    AActor* Target;
};"""

UNREAL_GAME_TEMPLATES["weather_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Particles/ParticleSystemComponent.h"
#include "WeatherComponent.generated.h"
UENUM(BlueprintType)
enum class EWeatherType : uint8 { Clear, Cloudy, Rain, Storm, Snow, Fog, Sandstorm };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWeatherChanged, EWeatherType, NewWeather);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UWeatherComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UWeatherComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weather") EWeatherType CurrentWeather = EWeatherType::Clear;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weather") float TransitionTime = 10.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weather") bool bRandomWeather  = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weather") float WeatherChangeInterval = 120.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") UParticleSystem* RainFX;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") UParticleSystem* SnowFX;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") UParticleSystem* StormFX;
    UPROPERTY(BlueprintAssignable) FOnWeatherChanged OnWeatherChanged;
    UFUNCTION(BlueprintCallable) void SetWeather(EWeatherType NewWeather);
    UFUNCTION(BlueprintCallable) void StartRandomWeather();
    UFUNCTION(BlueprintPure) float GetVisibilityMultiplier() const;
    UFUNCTION(BlueprintPure) float GetMovementPenalty() const;
    UFUNCTION(BlueprintPure) bool IsHazardous() const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle WeatherTimer;
    UParticleSystemComponent* ActiveFX;
    void ApplyWeatherEffects();
    void ChangeToRandomWeather();
};"""

UNREAL_GAME_TEMPLATES["status_effect"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StatusEffectComponent.generated.h"
UENUM(BlueprintType)
enum class EStatusEffect : uint8 { None, Poisoned, Burning, Frozen, Stunned, Slowed, Bleeding, Buffed };
USTRUCT(BlueprintType)
struct FActiveEffect
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EStatusEffect Type = EStatusEffect::None;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Duration  = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Magnitude = 10.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float TickRate  = 1.f;
    float TimeRemaining = 0.f;
    float TimeSinceLastTick = 0.f;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnEffectApplied, EStatusEffect, Effect);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnEffectRemoved, EStatusEffect, Effect);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UStatusEffectComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UStatusEffectComponent();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Effects") TArray<FActiveEffect> ActiveEffects;
    UPROPERTY(BlueprintAssignable) FOnEffectApplied OnEffectApplied;
    UPROPERTY(BlueprintAssignable) FOnEffectRemoved OnEffectRemoved;
    UFUNCTION(BlueprintCallable) void ApplyEffect(EStatusEffect Type, float Duration, float Magnitude);
    UFUNCTION(BlueprintCallable) void RemoveEffect(EStatusEffect Type);
    UFUNCTION(BlueprintCallable) void ClearAllEffects();
    UFUNCTION(BlueprintPure) bool HasEffect(EStatusEffect Type) const;
    UFUNCTION(BlueprintPure) float GetEffectMagnitude(EStatusEffect Type) const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["grappling_hook"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Cable/CableComponent.h"
#include "GrapplingHookComponent.generated.h"
UENUM(BlueprintType)
enum class EGrappleState : uint8 { Idle, Flying, Attached, Pulling, SwingArc };
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UGrapplingHookComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UGrapplingHookComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Grapple") float MaxRange      = 2000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Grapple") float PullSpeed     = 1200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Grapple") float SwingForce    = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Grapple") float Cooldown      = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Grapple") UCableComponent* Cable;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Grapple") EGrappleState State = EGrappleState::Idle;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Grapple") FVector GrapplePoint;
    UFUNCTION(BlueprintCallable) void FireGrapple(FVector TargetLocation);
    UFUNCTION(BlueprintCallable) void ReleaseGrapple();
    UFUNCTION(BlueprintCallable) void PullToPoint();
    UFUNCTION(BlueprintPure) bool CanGrapple() const;
    UFUNCTION(BlueprintPure) bool IsGrappling() const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
private:
    float LastGrappleTime = -999.f;
    ACharacter* OwnerCharacter;
};"""

UNREAL_GAME_TEMPLATES["combo_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ComboComponent.generated.h"
USTRUCT(BlueprintType)
struct FComboAttack
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString AttackName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Damage          = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Radius          = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float InputWindow     = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) class UAnimMontage* Animation;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnComboAttack, FString, AttackName, int32, ComboCount);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnComboFinisher, int32, TotalHits);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UComboComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UComboComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combo") TArray<FComboAttack> ComboChain;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combo") float ComboResetTime = 1.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combo") int32 DamageScaling  = 5;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combo") int32 CurrentCombo = 0;
    UPROPERTY(BlueprintAssignable) FOnComboAttack  OnComboAttack;
    UPROPERTY(BlueprintAssignable) FOnComboFinisher OnComboFinisher;
    UFUNCTION(BlueprintCallable) void InputAttack();
    UFUNCTION(BlueprintCallable) void ResetCombo();
    UFUNCTION(BlueprintPure) float GetCurrentDamage() const;
    UFUNCTION(BlueprintPure) int32 GetComboCount() const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle ComboResetTimer;
    float LastAttackTime = 0.f;
};"""

UNREAL_GAME_TEMPLATES["leaderboard"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LeaderboardComponent.generated.h"
USTRUCT(BlueprintType)
struct FLeaderboardEntry
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString PlayerName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   Score = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float   Time  = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Date;
    bool operator>(const FLeaderboardEntry& O) const { return Score > O.Score; }
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnLeaderboardUpdated);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API ULeaderboardComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    ULeaderboardComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Leaderboard") int32 MaxEntries = 10;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Leaderboard") TArray<FLeaderboardEntry> Entries;
    UPROPERTY(BlueprintAssignable) FOnLeaderboardUpdated OnLeaderboardUpdated;
    UFUNCTION(BlueprintCallable) void AddEntry(FString Name, int32 Score, float Time);
    UFUNCTION(BlueprintCallable) void ClearLeaderboard();
    UFUNCTION(BlueprintCallable) void SaveLeaderboard();
    UFUNCTION(BlueprintCallable) void LoadLeaderboard();
    UFUNCTION(BlueprintPure) int32 GetRank(int32 Score) const;
    UFUNCTION(BlueprintPure) TArray<FLeaderboardEntry> GetTopN(int32 N) const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["wave_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WaveManagerActor.generated.h"
USTRUCT(BlueprintType)
struct FWaveData
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<TSubclassOf<AActor>> EnemyTypes;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 EnemyCount    = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float SpawnInterval = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float WaveBonus     = 500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bHasBoss       = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaveStarted, int32, WaveNumber);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaveCompleted, int32, WaveNumber);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnAllWavesCompleted);
UCLASS()
class MYGAME_API AWaveManagerActor : public AActor
{
    GENERATED_BODY()
public:
    AWaveManagerActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves") TArray<FWaveData> Waves;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves") TArray<AActor*>   SpawnPoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Waves") float TimeBetweenWaves = 5.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Waves") int32 CurrentWave    = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Waves") int32 EnemiesAlive   = 0;
    UPROPERTY(BlueprintAssignable) FOnWaveStarted      OnWaveStarted;
    UPROPERTY(BlueprintAssignable) FOnWaveCompleted    OnWaveCompleted;
    UPROPERTY(BlueprintAssignable) FOnAllWavesCompleted OnAllWavesCompleted;
    UFUNCTION(BlueprintCallable) void StartWaves();
    UFUNCTION(BlueprintCallable) void OnEnemyKilled();
    UFUNCTION(BlueprintCallable) void SkipToWave(int32 WaveIndex);
    UFUNCTION(BlueprintPure) bool IsLastWave() const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle SpawnTimer;
    FTimerHandle WaveTimer;
    int32 SpawnedThisWave = 0;
    void BeginWave(int32 Index);
    void SpawnNextEnemy();
    void EndWave();
};"""

UNREAL_GAME_TEMPLATES["faction_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "FactionComponent.generated.h"
UENUM(BlueprintType)
enum class EFaction : uint8 { Player, Ally, Neutral, Enemy, Wildlife };
UENUM(BlueprintType)
enum class ERelation : uint8 { Friendly, Neutral, Hostile };
USTRUCT(BlueprintType)
struct FFactionRelation
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EFaction FactionA;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EFaction FactionB;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) ERelation Relation = ERelation::Neutral;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 ReputationScore = 0;
};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UFactionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UFactionComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Faction") EFaction MyFaction = EFaction::Neutral;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Faction") TArray<FFactionRelation> Relations;
    UFUNCTION(BlueprintCallable) ERelation GetRelationTo(EFaction Other) const;
    UFUNCTION(BlueprintCallable) void ChangeReputation(EFaction Target, int32 Amount);
    UFUNCTION(BlueprintPure) bool IsHostileTo(EFaction Other) const;
    UFUNCTION(BlueprintPure) bool IsFriendlyTo(EFaction Other) const;
    UFUNCTION(BlueprintPure) bool IsNeutralTo(EFaction Other) const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["destructible"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DestructibleActor.generated.h"
UENUM(BlueprintType)
enum class EDestructionStage : uint8 { Intact, Damaged, HeavilyDamaged, Destroyed };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDestroyed, AActor*, DestroyedActor);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnDamageStage, EDestructionStage, OldStage, EDestructionStage, NewStage);
UCLASS()
class MYGAME_API ADestructibleActor : public AActor
{
    GENERATED_BODY()
public:
    ADestructibleActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health") float MaxHealth    = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Health") float CurrentHealth;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stages") UStaticMesh* IntactMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stages") UStaticMesh* DamagedMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stages") UStaticMesh* DestroyedMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") UParticleSystem* DestructionFX;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Loot") TArray<TSubclassOf<AActor>> LootClasses;
    UPROPERTY(BlueprintAssignable) FOnDestroyed   OnDestroyed;
    UPROPERTY(BlueprintAssignable) FOnDamageStage OnDamageStage;
    UFUNCTION(BlueprintCallable) void ApplyDamage(float Damage, AActor* Instigator);
    UFUNCTION(BlueprintPure) EDestructionStage GetStage() const;
    UFUNCTION(BlueprintPure) float GetHealthPercent() const;
protected:
    virtual void BeginPlay() override;
private:
    UPROPERTY(VisibleAnywhere) UStaticMeshComponent* MeshComp;
    EDestructionStage CurrentStage = EDestructionStage::Intact;
    void UpdateStage();
    void SpawnLoot();
};"""

UNREAL_GAME_TEMPLATES["shop_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShopComponent.generated.h"
USTRUCT(BlueprintType)
struct FShopItem
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ItemName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   Price       = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   Stock       = -1; // -1 = infinite
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool    bUnlocked   = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<AActor> ItemClass;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnPurchase, FString, ItemName, int32, NewBalance);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnInsufficientFunds, int32, RequiredAmount);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UShopComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UShopComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Shop") TArray<FShopItem> ShopInventory;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Currency") FString CurrencyName = "Gold";
    UPROPERTY(BlueprintAssignable) FOnPurchase          OnPurchase;
    UPROPERTY(BlueprintAssignable) FOnInsufficientFunds OnInsufficientFunds;
    UFUNCTION(BlueprintCallable) bool BuyItem(int32 ItemIndex, int32 PlayerCurrency, int32& OutNewBalance);
    UFUNCTION(BlueprintCallable) bool SellItem(FString ItemName, int32 SellPrice, int32& OutNewBalance);
    UFUNCTION(BlueprintCallable) void RestockAll();
    UFUNCTION(BlueprintPure) TArray<FShopItem> GetAvailableItems() const;
    UFUNCTION(BlueprintPure) int32 GetItemPrice(int32 Index) const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["skill_tree"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "SkillTreeComponent.generated.h"
USTRUCT(BlueprintType)
struct FSkill
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString SkillName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   Cost          = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   MaxLevel      = 3;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 CurrentLevel  = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<int32> Prerequisites; // indices
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float StatBonus       = 10.f;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnSkillUnlocked, FString, SkillName, int32, NewLevel);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API USkillTreeComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    USkillTreeComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Skills") TArray<FSkill> Skills;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Skills") int32 SkillPoints = 0;
    UPROPERTY(BlueprintAssignable) FOnSkillUnlocked OnSkillUnlocked;
    UFUNCTION(BlueprintCallable) bool UnlockSkill(int32 Index);
    UFUNCTION(BlueprintCallable) bool CanUnlock(int32 Index) const;
    UFUNCTION(BlueprintCallable) void ResetSkills(bool bRefundPoints);
    UFUNCTION(BlueprintPure) float GetTotalBonus(FString StatName) const;
    UFUNCTION(BlueprintPure) TArray<int32> GetUnlockedSkills() const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["checkpoint_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CheckpointManager.generated.h"
USTRUCT(BlueprintType)
struct FCheckpointData
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector   SpawnLocation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FRotator  SpawnRotation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32     Score       = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32     Lives       = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float     Health      = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool      bActivated  = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCheckpointReached, int32, CheckpointIndex);
UCLASS()
class MYGAME_API ACheckpointManager : public AActor
{
    GENERATED_BODY()
public:
    ACheckpointManager();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Checkpoints") TArray<FCheckpointData> Checkpoints;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Checkpoints") int32 CurrentCheckpoint = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Checkpoints") int32 Lives               = 3;
    UPROPERTY(BlueprintAssignable) FOnCheckpointReached OnCheckpointReached;
    UFUNCTION(BlueprintCallable) void ActivateCheckpoint(int32 Index, AActor* Player);
    UFUNCTION(BlueprintCallable) void RespawnPlayer(AActor* Player);
    UFUNCTION(BlueprintCallable) void LoseLife();
    UFUNCTION(BlueprintPure) FCheckpointData GetCurrentCheckpoint() const;
    UFUNCTION(BlueprintPure) bool HasLivesLeft() const;
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["fishing_advanced"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "FishingComponent.generated.h"
UENUM(BlueprintType)
enum class EFishRarity : uint8 { Common, Uncommon, Rare, Epic, Legendary };
USTRUCT(BlueprintType)
struct FFishData
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString FishName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EFishRarity Rarity = EFishRarity::Common;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float MinWeight = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float MaxWeight = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float DropChance = 40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 SellPrice = 10;
};
UENUM(BlueprintType)
enum class EFishingState : uint8 { Idle, Casting, Waiting, Biting, Reeling, Success, Fail };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnFishCaught, FFishData, Fish, float, Weight);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UFishingComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UFishingComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fishing") TArray<FFishData> FishPool;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fishing") float CastDistance   = 1500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fishing") float MinBiteTime    = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fishing") float MaxBiteTime    = 15.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fishing") float ReelingWindow  = 2.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EFishingState State = EFishingState::Idle;
    UPROPERTY(BlueprintAssignable) FOnFishCaught OnFishCaught;
    UFUNCTION(BlueprintCallable) void Cast();
    UFUNCTION(BlueprintCallable) void Reel();
    UFUNCTION(BlueprintCallable) void CancelFishing();
    UFUNCTION(BlueprintPure) bool IsFishing() const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle BiteTimer;
    FTimerHandle ReelTimer;
    FFishData CurrentFish;
    void OnBite();
    void OnReelTimeout();
    FFishData RollFish();
};"""

UNREAL_GAME_TEMPLATES["building_placement"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BuildingComponent.generated.h"
UENUM(BlueprintType)
enum class EBuildState : uint8 { Idle, Placing, Confirming };
USTRUCT(BlueprintType)
struct FBuildingData
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString BuildingName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<AActor> BuildingClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Cost       = 50;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector Size     = FVector(200,200,200);
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSnapsToGrid = true;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBuildingPlaced, AActor*, Building);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UBuildingComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBuildingComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Build") TArray<FBuildingData> BuildingCatalog;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Build") float GridSize = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EBuildState State = EBuildState::Idle;
    UPROPERTY(BlueprintAssignable) FOnBuildingPlaced OnBuildingPlaced;
    UFUNCTION(BlueprintCallable) void StartPlacing(int32 CatalogIndex, int32 PlayerCurrency);
    UFUNCTION(BlueprintCallable) void ConfirmPlacement(FVector Location, FRotator Rotation, int32& OutCost);
    UFUNCTION(BlueprintCallable) void CancelPlacement();
    UFUNCTION(BlueprintCallable) void DemolishBuilding(AActor* Building, int32& OutRefund);
    UFUNCTION(BlueprintPure) FVector SnapToGrid(FVector Location) const;
    UFUNCTION(BlueprintPure) bool IsValidLocation(FVector Location) const;
protected:
    virtual void BeginPlay() override;
private:
    int32 CurrentBuildingIndex = -1;
    AActor* PreviewActor = nullptr;
};"""

UNREAL_GAME_TEMPLATES["camera_shake_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Camera/CameraShakeBase.h"
#include "CameraShakeManager.generated.h"
USTRUCT(BlueprintType)
struct FCameraShakePreset
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Name;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<UCameraShakeBase> ShakeClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Scale = 1.f;
};
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCameraShakeManager : public UActorComponent
{
    GENERATED_BODY()
public:
    UCameraShakeManager();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Shakes") TArray<FCameraShakePreset> Presets;
    UFUNCTION(BlueprintCallable) void PlayShake(FString Name, float ScaleOverride = 1.f);
    UFUNCTION(BlueprintCallable) void PlayShakeAtLocation(FString Name, FVector Location, float Radius);
    UFUNCTION(BlueprintCallable) void StopAllShakes();
    UFUNCTION(BlueprintCallable) void AddPreset(FCameraShakePreset Preset);
protected:
    virtual void BeginPlay() override;
private:
    APlayerCameraManager* CameraManager;
};"""

UNREAL_GAME_TEMPLATES["map_marker"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MapMarkerComponent.generated.h"
UENUM(BlueprintType)
enum class EMarkerType : uint8 { Player, Enemy, Ally, Objective, Treasure, Danger, Custom };
USTRUCT(BlueprintType)
struct FMapMarker
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString   Label;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector   WorldPosition;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EMarkerType Type = EMarkerType::Custom;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FLinearColor Color = FLinearColor::White;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float     Scale  = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool      bVisible = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) AActor*   TrackedActor = nullptr;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMarkerAdded, FMapMarker, Marker);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UMapMarkerComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UMapMarkerComponent();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Markers") TArray<FMapMarker> Markers;
    UPROPERTY(BlueprintAssignable) FOnMarkerAdded OnMarkerAdded;
    UFUNCTION(BlueprintCallable) int32 AddMarker(FMapMarker Marker);
    UFUNCTION(BlueprintCallable) void RemoveMarker(int32 Index);
    UFUNCTION(BlueprintCallable) void UpdateTrackedMarkers();
    UFUNCTION(BlueprintCallable) void SetMarkerVisible(int32 Index, bool bVisible);
    UFUNCTION(BlueprintCallable) void ClearAllMarkers();
    UFUNCTION(BlueprintPure) TArray<FMapMarker> GetMarkersByType(EMarkerType Type) const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["vr_interaction"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MotionControllerComponent.h"
#include "VRInteractionComponent.generated.h"
UENUM(BlueprintType)
enum class EGrabType : uint8 { None, Grip, Pinch, Palm };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnGrabbed, AActor*, GrabbedActor, EGrabType, GrabType);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnReleased, AActor*, ReleasedActor);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UVRInteractionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UVRInteractionComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VR") UMotionControllerComponent* MotionController;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VR") float GrabRadius    = 15.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VR") float ThrowForce    = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="VR") float HapticStrength= 0.5f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VR") AActor* GrabbedObject;
    UPROPERTY(BlueprintAssignable) FOnGrabbed  OnGrabbed;
    UPROPERTY(BlueprintAssignable) FOnReleased OnReleased;
    UFUNCTION(BlueprintCallable) void TryGrab();
    UFUNCTION(BlueprintCallable) void Release();
    UFUNCTION(BlueprintCallable) void Throw(FVector Direction);
    UFUNCTION(BlueprintCallable) void TriggerHaptic(float Frequency, float Amplitude);
    UFUNCTION(BlueprintPure) bool IsGrabbing() const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["terrain_deformation"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LandscapeComponent.h"
#include "TerrainDeformComponent.generated.h"
UENUM(BlueprintType)
enum class EDeformType : uint8 { Dig, Raise, Flatten, Smooth, Paint };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTerrainModified, FVector, Location, EDeformType, Type);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UTerrainDeformComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UTerrainDeformComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Terrain") ALandscape* TargetLandscape;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Terrain") float BrushRadius   = 200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Terrain") float BrushStrength = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Terrain") float BrushFalloff  = 0.7f;
    UPROPERTY(BlueprintAssignable) FOnTerrainModified OnTerrainModified;
    UFUNCTION(BlueprintCallable) void Deform(FVector WorldLocation, EDeformType Type);
    UFUNCTION(BlueprintCallable) void SetBrushSize(float Radius, float Strength);
    UFUNCTION(BlueprintCallable) void UndoLastDeformation();
protected:
    virtual void BeginPlay() override;
private:
    TArray<TArray<float>> UndoStack;
};"""

UNREAL_GAME_TEMPLATES["cutscene_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LevelSequenceActor.h"
#include "CutsceneManager.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCutsceneStart, FString, CutsceneName);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCutsceneEnd, FString, CutsceneName);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCutsceneManager : public UActorComponent
{
    GENERATED_BODY()
public:
    UCutsceneManager();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cutscenes") TMap<FString, ALevelSequenceActor*> Cutscenes;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cutscenes") bool bPauseGameDuring = true;
    UPROPERTY(BlueprintAssignable) FOnCutsceneStart OnCutsceneStart;
    UPROPERTY(BlueprintAssignable) FOnCutsceneEnd   OnCutsceneEnd;
    UFUNCTION(BlueprintCallable) void PlayCutscene(FString Name);
    UFUNCTION(BlueprintCallable) void SkipCutscene();
    UFUNCTION(BlueprintCallable) void StopCutscene();
    UFUNCTION(BlueprintPure) bool IsPlayingCutscene() const;
    UFUNCTION(BlueprintPure) FString GetCurrentCutsceneName() const;
protected:
    virtual void BeginPlay() override;
private:
    FString CurrentCutscene;
    bool bIsPlaying = false;
};"""

UNREAL_GAME_TEMPLATES["economy_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "EconomyComponent.generated.h"
UENUM(BlueprintType)
enum class ECurrency : uint8 { Gold, Silver, Gems, Tokens, Premium };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBalanceChanged, ECurrency, CurrencyType, int32, NewBalance);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTransaction, FString, Item, int32, Amount);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UEconomyComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEconomyComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Economy") int32 Gold    = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Economy") int32 Silver  = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Economy") int32 Gems    = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Economy") int32 Tokens  = 0;
    UPROPERTY(BlueprintAssignable) FOnBalanceChanged OnBalanceChanged;
    UPROPERTY(BlueprintAssignable) FOnTransaction    OnTransaction;
    UFUNCTION(BlueprintCallable) bool AddCurrency(ECurrency Type, int32 Amount);
    UFUNCTION(BlueprintCallable) bool SpendCurrency(ECurrency Type, int32 Amount);
    UFUNCTION(BlueprintCallable) bool TransferCurrency(ECurrency Type, int32 Amount, UEconomyComponent* Target);
    UFUNCTION(BlueprintPure) int32 GetBalance(ECurrency Type) const;
    UFUNCTION(BlueprintPure) bool CanAfford(ECurrency Type, int32 Amount) const;
    UFUNCTION(BlueprintCallable) void SaveWallet();
    UFUNCTION(BlueprintCallable) void LoadWallet();
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["ai_perception"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AISenseConfig_Sight.h"
#include "Perception/AISenseConfig_Hearing.h"
#include "AIPerceptionManagerComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTargetSpotted, AActor*, Target, FVector, Location);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTargetLost, AActor*, Target);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnNoiseHeard, AActor*, Source, FVector, Location);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAIPerceptionManagerComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UAIPerceptionManagerComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Sight")   float SightRadius      = 1200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Sight")   float SightAngle       = 90.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Sight")   float LoseSightRadius  = 1500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hearing") float HearingRadius    = 600.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TArray<AActor*> PerceivedActors;
    UPROPERTY(BlueprintAssignable) FOnTargetSpotted OnTargetSpotted;
    UPROPERTY(BlueprintAssignable) FOnTargetLost    OnTargetLost;
    UPROPERTY(BlueprintAssignable) FOnNoiseHeard    OnNoiseHeard;
    UFUNCTION(BlueprintCallable) void SetSightRange(float Radius, float Angle);
    UFUNCTION(BlueprintCallable) void SetHearingRange(float Radius);
    UFUNCTION(BlueprintPure) bool CanSeeActor(AActor* Target) const;
    UFUNCTION(BlueprintPure) AActor* GetClosestPerceivedActor() const;
protected:
    virtual void BeginPlay() override;
    UPROPERTY() UAIPerceptionComponent* PerceptionComp;
    UFUNCTION() void OnPerceptionUpdated(const TArray<AActor*>& UpdatedActors);
};"""

UNREAL_GAME_TEMPLATES["achievement_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AchievementComponent.generated.h"
UENUM(BlueprintType)
enum class EAchievementType : uint8 { Counter, Boolean, Cumulative, Timed };
USTRUCT(BlueprintType)
struct FAchievement
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ID;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Title;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EAchievementType Type = EAchievementType::Counter;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float   Goal          = 1.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float Progress      = 0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool  bUnlocked     = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   RewardPoints  = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool    bHidden       = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAchievementUnlocked, FAchievement, Achievement);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAchievementComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UAchievementComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Achievements") TArray<FAchievement> Achievements;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Achievements") int32 TotalPoints = 0;
    UPROPERTY(BlueprintAssignable) FOnAchievementUnlocked OnAchievementUnlocked;
    UFUNCTION(BlueprintCallable) void UpdateProgress(FString AchievementID, float Amount);
    UFUNCTION(BlueprintCallable) void UnlockAchievement(FString AchievementID);
    UFUNCTION(BlueprintCallable) void ResetAchievement(FString AchievementID);
    UFUNCTION(BlueprintPure) float GetProgress(FString AchievementID) const;
    UFUNCTION(BlueprintPure) bool IsUnlocked(FString AchievementID) const;
    UFUNCTION(BlueprintPure) TArray<FAchievement> GetUnlockedAchievements() const;
    UFUNCTION(BlueprintCallable) void SaveAchievements();
    UFUNCTION(BlueprintCallable) void LoadAchievements();
protected:
    virtual void BeginPlay() override;
};"""


UNREAL_GAME_KEYWORDS.update({
    "shooter_character": ["fps character", "tps character", "shooter player", "gunner character", "armed character"],
    "rpg_stats": ["stats", "attributes", "strength", "dexterity", "level up", "experience", "stat block"],
    "loot_system": ["loot", "drop", "item rarity", "loot table", "drop rate", "random loot"],
    "crafting_system": ["crafting", "craft recipe", "workbench", "combine items", "craft system"],
    "stamina_system": ["stamina", "endurance", "sprint cost", "stamina bar", "exhaust"],
    "stealth_system": ["stealth", "visibility", "noise", "detection", "sight cone", "sneak"],
    "vehicle_component": ["vehicle", "car", "truck", "tank", "drive", "driving", "wheeled"],
    "network_component": ["network", "replicated", "multiplayer", "server", "client", "netcode", "mirror", "photon"],
    "procedural_dungeon": ["procedural dungeon", "dungeon generation", "random dungeon", "floor generation"],
    "boss_fight": ["boss", "boss fight", "boss phase", "final boss", "raid boss"],
    "weather_system": ["weather", "rain system", "snow system", "storm", "fog system", "climate"],
    "status_effect": ["status effect", "poison", "burn", "freeze", "stun", "slow", "bleed", "buff", "debuff"],
    "grappling_hook": ["grapple", "grappling hook", "swing", "zipline", "hook shot"],
    "combo_system": ["combo", "combo chain", "attack combo", "beat em up combo", "fighting combo"],
    "leaderboard": ["leaderboard", "high score", "top score", "ranking", "scoreboard"],
    "wave_manager": ["wave manager", "wave spawner", "horde", "enemy waves", "tower defense waves"],
    "faction_system": ["faction", "reputation", "alliance", "enemy faction", "team", "diplomacy"],
    "destructible": ["destructible", "breakable", "destroy object", "physics destruction", "crumble"],
    "shop_system": ["shop", "store", "buy", "sell", "merchant", "vendor", "purchase"],
    "skill_tree": ["skill tree", "skill", "perk", "talent tree", "upgrade tree", "passive"],
    "checkpoint_manager": ["checkpoint", "respawn", "lives", "save point", "midpoint"],
    "fishing_advanced": ["fishing", "fish catch", "fishing rod", "fish rarity", "angling"],
    "building_placement": ["building", "place building", "construction", "base building", "build mode", "city builder"],
    "camera_shake_manager": ["camera shake", "screen shake", "impact shake", "explosion shake"],
    "map_marker": ["map marker", "waypoint", "objective marker", "ping", "mark location"],
    "vr_interaction": ["vr", "virtual reality", "xr", "grab", "motion controller", "oculus", "quest", "hand tracking"],
    "terrain_deformation": ["terrain", "landscape", "dig", "raise", "modify terrain", "voxel terrain", "destroy ground"],
    "cutscene_manager": ["cutscene", "cinematic", "sequence", "level sequence", "story scene"],
    "economy_system": ["economy", "currency", "gold", "balance", "wallet", "coins", "premium currency"],
    "ai_perception": ["ai perception", "sight sense", "hearing sense", "perception", "spot enemy"],
    "achievement_system": ["achievement", "trophy", "badge", "unlock", "accomplishment", "challenge"],
})

def get_unreal_template(name: str, role: str = None) -> str:
    """Get Unreal header template by name or role — checks all keywords."""
    nl = name.lower()
    for key, keywords in UNREAL_GAME_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            tpl = UNREAL_GAME_TEMPLATES.get(key, "")
            if tpl: return tpl
    if role and role in UNREAL_GAME_TEMPLATES:
        return UNREAL_GAME_TEMPLATES[role]
    return ""

def save_unreal_scripts(matches: list, folder_name: str) -> bool:
    """
    Validate and save Unreal .h + .cpp files.
    Called from extract_and_save_scripts when domain == 'unreal'.
    """
    import os, re

    if len(matches) < 2:
        print("❌ Unreal requires header and cpp blocks.")
        return False

    header_code = matches[0].strip()
    cpp_code    = matches[1].strip()

    # Validate + auto-fix header
    is_valid, msg = validate_unreal(header_code)
    if not is_valid and "generated.h" in msg:
        print("⚠ Missing .generated.h — attempting auto-fix...")
        header_code, fixed = auto_fix_unreal_header(header_code)
        if fixed:
            is_valid, msg = validate_unreal(header_code)

    if not is_valid:
        print(f"❌ Validation Failed: {msg}")
        return False

    if "::" not in cpp_code:
        print("❌ Unreal CPP missing implementation (:: not found)")
        return False

    # Structural validation
    cpp_class_names = set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)::'  , cpp_code))
    known_overrides = {"BeginPlay","TickComponent","EndPlay","InitializeComponent",
                       "GetLifetimeReplicatedProps","SetupInputComponent","PostInitializeComponents"}
    header_clean    = re.sub(r'\b(UFUNCTION|UPROPERTY|UCLASS|USTRUCT|UENUM)\s*\([^)]*\)', '', header_code)
    declared_funcs  = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:const\s*)?;', header_clean))
    implemented     = re.findall(r'::([A-Za-z_][A-Za-z0-9_]*)\s*\(', cpp_code)

    for func in implemented:
        if func in cpp_class_names or func.lstrip('~') in cpp_class_names: continue
        if func in known_overrides: continue
        if func not in declared_funcs:
            print(f"⚠ Note: '{func}' not in header — treating as override.")

    # Extract class name and save
    m = re.search(r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", header_code)
    class_name  = m.group(1) if m else "UnrealClass"
    header_path = os.path.join(folder_name, f"{class_name}.h")
    cpp_path    = os.path.join(folder_name, f"{class_name}.cpp")

    with open(header_path, "w", encoding="utf-8") as f: f.write(header_code)
    with open(cpp_path,    "w", encoding="utf-8") as f: f.write(cpp_code)

    print(f"\n💾 Saved -> {header_path}")
    print(f"💾 Saved -> {cpp_path}")
    return True
