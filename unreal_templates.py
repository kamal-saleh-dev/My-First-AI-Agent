# unreal_templates.py — Unreal Engine C++ validation, fixes, and prompts
# Edit here without touching agent.py
import re

def fix_generated_h_name(header_code):
    """Auto-fix .generated.h to match actual class name."""
    import re
    cls_match = re.search(r'class\s+\w+\s+(\w+)\s*:', header_code)
    if not cls_match:
        return header_code
    cls_name = cls_match.group(1)
    # Replace any wrong .generated.h with correct one
    fixed = re.sub(r'#include\s+"[^"]+\.generated\.h"',
                   f'#include "{cls_name}.generated.h"', header_code)
    return fixed

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

CRITICAL INHERITANCE RULES:
- NEVER use AProjectileBase — it does NOT exist in Unreal Engine
- AIController → inherit AAIController, NOT ACharacter
- NEVER mix: if named "EnemyController" → inherit AAIController
- PlayerCharacter → inherit ACharacter (correct)
- Projectiles inherit from: AActor (add UProjectileMovementComponent manually)
- Characters inherit from: ACharacter
- Controllers inherit from: APlayerController
- Components inherit from: UActorComponent
- NEVER invent base classes that don't exist in Unreal Engine

CRITICAL C++ SYNTAX:
- IsValid check: if (IsValid(EnemyClass)) — NOT "if (EnemyClass IsValid())"
- Null check: if (EnemyClass) or if (IsValid(EnemyClass))
- SpawnActor: GetWorld()->SpawnActor<AActor>(EnemyClass, Location, Rotation)

CRITICAL RULES FOR .generated.h:
- If class is named AMyPlayerController → include "AMyPlayerController.generated.h"
- If class is named AEnemyAI → include "AEnemyAI.generated.h"  
- ALWAYS match the .generated.h filename to the EXACT class name (with A/U prefix)
- NEVER use generic names like "MyComp.generated.h" or "EnemyAI.generated.h"

CRITICAL RULES FOR FUNCTION BODIES:
- ALL declared functions MUST have real implementations — NO placeholder comments
- NEVER write "// Implement logic", "// Handle death", "// TODO", "// Add logic here"
- SetupInputComponent: MUST call BindAxis("MoveForward",...) BindAxis("MoveRight",...) BindAction("Fire",...)
- AI Tick: MUST call SetActorLocation or AddMovementInput toward target
- OnHit/Overlap: MUST call TakeDamage and Destroy(this)
- TakeDamage: MUST reduce CurrentHealth and call Die() if <=0
- Die(): MUST call Destroy(GetOwner()) or GetOwner()->Destroy()
- Explode(): MUST call Destroy(this) and optionally spawn particles
- Any function with "// Handle X" = VIOLATION — write actual code

CRITICAL RULES FOR UPROPERTY INITIALIZATION:
- ALL float/int/bool UPROPERTY must have = default_value in header
- MoveSpeed MUST be initialized: float MoveSpeed = 600.f
- MaxHealth MUST be initialized: float MaxHealth = 100.f
- CurrentHealth MUST be initialized: float CurrentHealth = 100.f  
- AttackDamage MUST be initialized: float AttackDamage = 20.f
- DetectionRadius MUST be initialized: float DetectionRadius = 800.f
- NEVER leave numeric properties uninitialized


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
    float CurrentHealth = 100.f;
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
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats") int32 CurrentHealth = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") float FireRate = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float MoveSpeed = 600.f;
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


def auto_fix_unreal_code(header_code: str, cpp_code: str, class_name: str) -> tuple:
    """
    Auto-fix common Unreal C++ issues in both header and CPP.
    Returns (fixed_header, fixed_cpp)
    """
    # Fix 1: Wrong #include name in CPP (EnemySpawner.h -> AEnemySpawner.h)
    cpp_code = re.sub(
        r'#include\s+"[A-Za-z][A-Za-z0-9_]*\.h"',
        f'#include "{class_name}.h"',
        cpp_code, count=1
    )

    # Fix 2: Self-inheritance (APlayerController : public APlayerController)
    self_inh = re.search(r'class\s+\w+\s+(\w+)\s*:\s*public\s+\1\b', header_code)
    if self_inh:
        bad = self_inh.group(1)
        new_cls = "AMy" + bad.lstrip('A') if bad.startswith('A') else "U" + bad
        header_code = header_code.replace(
            bad + " : public " + bad,
            new_cls + " : public " + bad
        )
        cpp_code = cpp_code.replace(bad + "::", new_cls + "::")

    # Fix 3: Destroy(this) -> Destroy()
    cpp_code = re.sub(r'Destroy\s*\(\s*this\s*\)', 'Destroy()', cpp_code)

    # Fix 3b: UActorComponent calling AddMovementInput directly — must cast owner
    if "UActorComponent" in header_code and "AddMovementInput" in cpp_code:
        import re as _re
        cpp_code = _re.sub(
            r'AddMovementInput\(([^)]+)\)',
            lambda m: (
                "{ ACharacter* _Ch = Cast<ACharacter>(GetOwner()); "
                "if (_Ch) _Ch->GetMovementComponent()->AddInputVector(" + m.group(1) + "); }"
            ),
            cpp_code
        )

    # Fix 4: AActor spawner using GetOwner()->GetActorRotation()
    if "public AActor" in header_code:
        cpp_code = cpp_code.replace("GetOwner()->GetActorRotation()", "GetActorRotation()")

    # Fix 5: SpawnEnemy not declared in header but used in CPP
    if "SpawnEnemy" in cpp_code and "SpawnEnemy" not in header_code:
        header_code = header_code.replace(
            "virtual void BeginPlay() override;",
            "virtual void BeginPlay() override;\n    void SpawnEnemy();"
        )

    # Fix 6: EnemyClass used in CPP but not declared in header
    if "EnemyClass" in cpp_code and "EnemyClass" not in header_code:
        header_code = header_code.replace(
            "GENERATED_BODY()\npublic:",
            "GENERATED_BODY()\npublic:\n    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=\"Spawning\")\n    TSubclassOf<AActor> EnemyClass;"
        )

    # Fix 7: SpawnTimerHandle used in CPP but not declared
    if "SpawnTimerHandle" in cpp_code and "SpawnTimerHandle" not in header_code:
        if "private:" in header_code:
            header_code = header_code.replace(
                "private:",
                "private:\n    FTimerHandle SpawnTimerHandle;"
            )
        else:
            header_code = header_code.replace(
                "protected:",
                "private:\n    FTimerHandle SpawnTimerHandle;\nprotected:"
            )

    # Fix 8: SetTarget used in CPP but not declared in header
    if "SetTarget(" in cpp_code and "SetTarget" not in header_code:
        header_code = header_code.replace(
            "private:",
            "public:\n    UFUNCTION(BlueprintCallable)\n    void SetTarget(ACharacter* NewTarget);\nprivate:"
        )

    # Fix 9: UpdateTarget in CPP but not declared
    if "UpdateTarget(" in cpp_code and "UpdateTarget" not in header_code:
        if "private:" in header_code:
            header_code = header_code.replace(
                "private:",
                "private:\n    void UpdateTarget();"
            )

    # Fix 10: Die() in CPP but not declared in header
    if ("::Die()" in cpp_code or "    Die();" in cpp_code or "Die();" in cpp_code) and "void Die()" not in header_code:
        if "void TakeDamage" in header_code:
            header_code = header_code.replace(
                "void TakeDamage",
                "void Die();\n    void TakeDamage"
            )

    # Fix 11: SpawnProjectile declared but not implemented
    if "SpawnProjectile()" in header_code and "SpawnProjectile()" not in cpp_code:
        m = re.search(r'class\s+\w+\s+(\w+)\s*:', header_code)
        cname = m.group(1) if m else class_name
        cpp_code = cpp_code.rstrip() + (
            "\n\nvoid " + cname + "::SpawnProjectile()\n"
            "{\n"
            "    if (IsValid(ProjectileClass))\n"
            "    {\n"
            "        FVector Loc = GetOwner()->GetActorLocation() + GetOwner()->GetActorForwardVector() * 100.f;\n"
            "        FRotator Rot = GetOwner()->GetActorRotation();\n"
            "        GetWorld()->SpawnActor<AActor>(ProjectileClass, Loc, Rot);\n"
            "    }\n"
            "}\n"
        )

    # Fix 12: Missing UProjectileMovementComponent include
    if "UProjectileMovementComponent" in (header_code + cpp_code):
        if "ProjectileMovementComponent.h" not in header_code:
            header_code = header_code.replace(
                "#include \"CoreMinimal.h\"",
                "#include \"CoreMinimal.h\"\n#include \"GameFramework/ProjectileMovementComponent.h\""
            )

    # Fix 13: UGameplayStatics used without include
    if "UGameplayStatics" in cpp_code and "Kismet/GameplayStatics.h" not in cpp_code:
        cpp_code = cpp_code.replace(
            '#include "' + class_name + '.h"',
            '#include "' + class_name + '.h"\n#include "Kismet/GameplayStatics.h"'
        )

    # Fix 14: OnHit binding needs UFUNCTION
    if "AddDynamic(this, &" in cpp_code and "OnHit" in header_code:
        header_code = re.sub(
            r'(\s+)void OnHit\(',
            r'\1UFUNCTION()\n\1void OnHit(',
            header_code
        )
        # Deduplicate if already there
        header_code = header_code.replace(
            "UFUNCTION()\n    UFUNCTION()\n",
            "UFUNCTION()\n"
        )

    return header_code, cpp_code

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

def get_unreal_cpp_template(name: str, role: str = None) -> str:
    """Get matching CPP implementation template."""
    nl = name.lower()
    for key, keywords in UNREAL_GAME_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            tpl = UNREAL_GAME_TEMPLATES_CPP.get(key, "")
            if tpl: return tpl
    if role: return UNREAL_GAME_TEMPLATES_CPP.get(role, "")
    return ""

# ── NEW COMPREHENSIVE TEMPLATES ─────────────────────────────────

UNREAL_GAME_TEMPLATES["health_regeneration"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "HealthRegenComponent.generated.h"
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UHealthRegenComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UHealthRegenComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health") float MaxHealth = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Health") float CurrentHealth = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Regen") float RegenRate = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Regen") float RegenDelay = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Regen") bool bRegenEnabled = true;
    UFUNCTION(BlueprintCallable) void TakeDamage(float Damage);
    UFUNCTION(BlueprintCallable) void Heal(float Amount);
    UFUNCTION(BlueprintPure) float GetHealthPercent() const;
    UFUNCTION(BlueprintPure) bool IsAlive() const { return CurrentHealth > 0.f; }
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
private:
    float TimeSinceDamage = 0.f;
    void Die();
};"""

UNREAL_GAME_TEMPLATES["armor_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ArmorComponent.generated.h"
UENUM(BlueprintType) enum class EArmorType : uint8 { Light, Medium, Heavy, Shield };
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UArmorComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UArmorComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Armor") EArmorType ArmorType = EArmorType::Medium;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Armor") float MaxArmor = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Armor") float CurrentArmor = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Armor") float DamageReduction = 0.3f;
    UFUNCTION(BlueprintCallable) float AbsorbDamage(float IncomingDamage);
    UFUNCTION(BlueprintCallable) void RepairArmor(float Amount);
    UFUNCTION(BlueprintPure) float GetArmorPercent() const;
    UFUNCTION(BlueprintPure) bool HasArmor() const { return CurrentArmor > 0.f; }
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["projectile_actor"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "Components/SphereComponent.h"
#include "ProjectileActor.generated.h"
UCLASS()
class MYGAME_API AProjectileActor : public AActor {
    GENERATED_BODY()
public:
    AProjectileActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Damage") float Damage = 25.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Damage") float Lifetime = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Damage") float ExplosionRadius = 0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) USphereComponent* CollisionComp;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) UProjectileMovementComponent* ProjectileMovement;
    UFUNCTION(BlueprintCallable) void SetDamage(float NewDamage) { Damage = NewDamage; }
    UFUNCTION(BlueprintCallable) void SetVelocity(FVector Velocity);
protected:
    virtual void BeginPlay() override;
private:
    UFUNCTION() void OnHit(UPrimitiveComponent* HitComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit);
    UFUNCTION() void OnOverlap(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);
};"""

UNREAL_GAME_TEMPLATES["enemy_spawner"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EnemySpawnerActor.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnEnemySpawned, AActor*, Enemy);
UCLASS()
class MYGAME_API AEnemySpawnerActor : public AActor {
    GENERATED_BODY()
public:
    AEnemySpawnerActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spawn") TSubclassOf<AActor> EnemyClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spawn") float SpawnInterval = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spawn") int32 MaxEnemies = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Spawn") float SpawnRadius = 300.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Spawn") int32 EnemiesAlive = 0;
    UPROPERTY(BlueprintAssignable) FOnEnemySpawned OnEnemySpawned;
    UFUNCTION(BlueprintCallable) void StartSpawning();
    UFUNCTION(BlueprintCallable) void StopSpawning();
    UFUNCTION(BlueprintCallable) void OnEnemyKilled();
    UFUNCTION(BlueprintPure) bool CanSpawn() const { return IsValid(EnemyClass) && EnemiesAlive < MaxEnemies; }
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle SpawnTimer;
    UFUNCTION() void SpawnEnemy();
};"""

UNREAL_GAME_TEMPLATES["player_character"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "PlayerCharacterBase.generated.h"
UCLASS()
class MYGAME_API APlayerCharacterBase : public ACharacter {
    GENERATED_BODY()
public:
    APlayerCharacterBase();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera") USpringArmComponent* CameraBoom;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera") UCameraComponent* FollowCamera;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float MaxHealth = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats") float CurrentHealth = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float WalkSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Movement") float SprintSpeed = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") TSubclassOf<AActor> ProjectileClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") float FireCooldown = 0.2f;
    UFUNCTION(BlueprintCallable) void TakeDamage(float Damage);
    UFUNCTION(BlueprintCallable) void Heal(float Amount);
    UFUNCTION(BlueprintCallable) void Sprint(bool bSprint);
    UFUNCTION(BlueprintCallable) void Fire();
    UFUNCTION(BlueprintPure) float GetHealthPercent() const { return MaxHealth > 0.f ? CurrentHealth / MaxHealth : 0.f; }
protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
private:
    float LastFireTime = -999.f;
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Die();
};"""

UNREAL_GAME_TEMPLATES["enemy_character"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "EnemyCharacterBase.generated.h"
UENUM(BlueprintType) enum class EEnemyState : uint8 { Idle, Patrol, Chase, Attack, Dead };
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnEnemyDied);
UCLASS()
class MYGAME_API AEnemyCharacterBase : public ACharacter {
    GENERATED_BODY()
public:
    AEnemyCharacterBase();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float MaxHealth = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Stats") float CurrentHealth = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float AttackDamage = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float DetectionRadius = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float AttackRange = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="AI") float MoveSpeed = 400.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="AI") EEnemyState State = EEnemyState::Idle;
    UPROPERTY(BlueprintAssignable) FOnEnemyDied OnEnemyDied;
    UFUNCTION(BlueprintCallable) void TakeDamage(float Damage);
    UFUNCTION(BlueprintCallable) void SetTarget(AActor* NewTarget);
    UFUNCTION(BlueprintPure) bool IsAlive() const { return CurrentHealth > 0.f; }
protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
private:
    AActor* Target;
    TArray<AActor*> PatrolPoints;
    int32 PatrolIndex = 0;
    void UpdateAI(float DeltaTime);
    void Die();
    void AttackTarget();
};"""

UNREAL_GAME_TEMPLATES["game_mode_base"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "CustomGameMode.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnGameOver);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnGameWin);
UCLASS()
class MYGAME_API ACustomGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    ACustomGameMode();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Game") int32 ScorePerKill = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Game") int32 StartingLives = 3;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Game") int32 CurrentScore = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Game") int32 CurrentLives = 3;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Game") int32 CurrentWave = 1;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Game") bool bGameOver = false;
    UPROPERTY(BlueprintAssignable) FOnGameOver OnGameOver;
    UPROPERTY(BlueprintAssignable) FOnGameWin  OnGameWin;
    UFUNCTION(BlueprintCallable) void AddScore(int32 Amount);
    UFUNCTION(BlueprintCallable) void OnEnemyKilled();
    UFUNCTION(BlueprintCallable) void OnPlayerDied();
    UFUNCTION(BlueprintCallable) void NextWave();
    UFUNCTION(BlueprintCallable) void GameOver();
    UFUNCTION(BlueprintCallable) void Win();
    UFUNCTION(BlueprintCallable) void RestartGame();
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["pickup_actor"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PickupActorBase.generated.h"
UENUM(BlueprintType) enum class EPickupType : uint8 { Health, Ammo, Armor, Speed, Score, Weapon, Key };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnPickedUp, AActor*, Collector, EPickupType, Type);
UCLASS()
class MYGAME_API APickupActorBase : public AActor {
    GENERATED_BODY()
public:
    APickupActorBase();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") EPickupType PickupType = EPickupType::Health;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") float Value = 25.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") bool bDestroyOnPickup = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Pickup") float RespawnTime = 30.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") bool bRotate = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FX") float RotateSpeed = 90.f;
    UPROPERTY(BlueprintAssignable) FOnPickedUp OnPickedUp;
    UFUNCTION(BlueprintCallable) void EnablePickup();
    UFUNCTION(BlueprintCallable) void DisablePickup();
protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    UPROPERTY(VisibleAnywhere) class USphereComponent* PickupSphere;
    UPROPERTY(VisibleAnywhere) class UStaticMeshComponent* PickupMesh;
private:
    UFUNCTION() void OnOverlap(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);
    bool bIsActive = true;
};"""

UNREAL_GAME_TEMPLATES["trigger_zone"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TriggerZoneActor.generated.h"
UENUM(BlueprintType) enum class ETriggerEvent : uint8 { OnEnter, OnExit, OnStay };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTrigger, AActor*, Actor, ETriggerEvent, Event);
UCLASS()
class MYGAME_API ATriggerZoneActor : public AActor {
    GENERATED_BODY()
public:
    ATriggerZoneActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Trigger") bool bPlayerOnly = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Trigger") bool bOneShot = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Trigger") float StayInterval = 1.f;
    UPROPERTY(BlueprintAssignable) FOnTrigger OnTrigger;
    UFUNCTION(BlueprintCallable) void SetEnabled(bool bEnabled);
    UFUNCTION(BlueprintPure) bool IsEnabled() const { return bIsEnabled; }
protected:
    virtual void BeginPlay() override;
    UPROPERTY(VisibleAnywhere) class UBoxComponent* TriggerBox;
private:
    bool bIsEnabled = true;
    bool bFired = false;
    FTimerHandle StayTimer;
    UFUNCTION() void OnBeginOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32, bool, const FHitResult&);
    UFUNCTION() void OnEndOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32);
};"""

UNREAL_GAME_TEMPLATES["respawn_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "RespawnComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnRespawn, FVector, RespawnLocation);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API URespawnComponent : public UActorComponent {
    GENERATED_BODY()
public:
    URespawnComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Respawn") float RespawnDelay = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Respawn") int32 MaxRespawns = -1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Respawn") bool bRespawnAtCheckpoint = true;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Respawn") int32 RespawnCount = 0;
    UPROPERTY(BlueprintAssignable) FOnRespawn OnRespawn;
    UFUNCTION(BlueprintCallable) void Die();
    UFUNCTION(BlueprintCallable) void SetCheckpoint(FVector Location);
    UFUNCTION(BlueprintPure) bool CanRespawn() const;
protected:
    virtual void BeginPlay() override;
private:
    FVector CheckpointLocation;
    FTimerHandle RespawnTimer;
    void DoRespawn();
};"""

UNREAL_GAME_TEMPLATES["score_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ScoreManagerComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnScoreChanged, int32, NewScore, int32, Delta);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnHighScore, int32, HighScore);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UScoreManagerComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UScoreManagerComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Score") int32 ScoreMultiplier = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Score") float MultiplierDuration = 5.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Score") int32 CurrentScore = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Score") int32 HighScore = 0;
    UPROPERTY(BlueprintAssignable) FOnScoreChanged OnScoreChanged;
    UPROPERTY(BlueprintAssignable) FOnHighScore    OnHighScore;
    UFUNCTION(BlueprintCallable) void AddScore(int32 Amount);
    UFUNCTION(BlueprintCallable) void SetMultiplier(int32 Multiplier);
    UFUNCTION(BlueprintCallable) void ResetScore();
    UFUNCTION(BlueprintCallable) void SaveHighScore();
    UFUNCTION(BlueprintCallable) void LoadHighScore();
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle MultiplierTimer;
    void ResetMultiplier();
};"""

UNREAL_GAME_TEMPLATES["ammo_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AmmoComponent.generated.h"
UENUM(BlueprintType) enum class EAmmoType : uint8 { Pistol, Rifle, Shotgun, Sniper, Rocket, Grenade };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAmmoChanged, EAmmoType, Type, int32, Remaining);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnReloadComplete, EAmmoType, Type);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAmmoComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UAmmoComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ammo") EAmmoType CurrentAmmoType = EAmmoType::Pistol;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ammo") int32 MagazineSize = 30;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ammo") int32 CurrentMagazine = 30;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ammo") int32 ReserveAmmo = 120;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ammo") float ReloadTime = 2.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ammo") bool bIsReloading = false;
    UPROPERTY(BlueprintAssignable) FOnAmmoChanged    OnAmmoChanged;
    UPROPERTY(BlueprintAssignable) FOnReloadComplete OnReloadComplete;
    UFUNCTION(BlueprintCallable) bool TryShoot();
    UFUNCTION(BlueprintCallable) void StartReload();
    UFUNCTION(BlueprintCallable) void AddAmmo(EAmmoType Type, int32 Amount);
    UFUNCTION(BlueprintPure) bool CanShoot() const { return CurrentMagazine > 0 && !bIsReloading; }
    UFUNCTION(BlueprintPure) bool NeedsReload() const { return CurrentMagazine < MagazineSize && ReserveAmmo > 0; }
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle ReloadTimer;
    void FinishReload();
};"""

UNREAL_GAME_TEMPLATES["door_system"] = """#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DoorActor.generated.h"
UENUM(BlueprintType) enum class EDoorState : uint8 { Closed, Opening, Open, Closing, Locked };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDoorStateChanged, EDoorState, NewState);
UCLASS()
class MYGAME_API ADoorActor : public AActor {
    GENERATED_BODY()
public:
    ADoorActor();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Door") float OpenAngle = 90.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Door") float OpenSpeed = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Door") bool bAutoClose = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Door") float AutoCloseDelay = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Door") bool bStartLocked = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Door") EDoorState State = EDoorState::Closed;
    UPROPERTY(BlueprintAssignable) FOnDoorStateChanged OnDoorStateChanged;
    UFUNCTION(BlueprintCallable) void Open();
    UFUNCTION(BlueprintCallable) void Close();
    UFUNCTION(BlueprintCallable) void Lock();
    UFUNCTION(BlueprintCallable) void Unlock();
    UFUNCTION(BlueprintCallable) void Toggle();
    UFUNCTION(BlueprintPure) bool IsOpen() const   { return State == EDoorState::Open; }
    UFUNCTION(BlueprintPure) bool IsLocked() const { return State == EDoorState::Locked; }
protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    UPROPERTY(VisibleAnywhere) UStaticMeshComponent* DoorMesh;
private:
    FRotator TargetRotation;
    FTimerHandle AutoCloseTimer;
};"""

UNREAL_GAME_TEMPLATES["level_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LevelManagerComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLevelLoad, FString, LevelName);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLoadProgress, float, Progress);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API ULevelManagerComponent : public UActorComponent {
    GENERATED_BODY()
public:
    ULevelManagerComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Levels") TArray<FString> LevelNames;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Levels") float LoadingScreenDelay = 0.5f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Levels") int32 CurrentLevelIndex = 0;
    UPROPERTY(BlueprintAssignable) FOnLevelLoad     OnLevelLoad;
    UPROPERTY(BlueprintAssignable) FOnLoadProgress  OnLoadProgress;
    UFUNCTION(BlueprintCallable) void LoadLevel(FString LevelName);
    UFUNCTION(BlueprintCallable) void LoadLevelByIndex(int32 Index);
    UFUNCTION(BlueprintCallable) void LoadNextLevel();
    UFUNCTION(BlueprintCallable) void ReloadCurrentLevel();
    UFUNCTION(BlueprintCallable) void LoadMainMenu();
    UFUNCTION(BlueprintPure) bool HasNextLevel() const { return CurrentLevelIndex + 1 < LevelNames.Num(); }
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["buff_debuff"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BuffDebuffComponent.generated.h"
UENUM(BlueprintType) enum class EBuffType : uint8 { DamageBoost, SpeedBoost, DefenseBoost, Invincible, Invisible, Regen, Poison, Slow, Stun, Burn };
USTRUCT(BlueprintType)
struct FBuff { GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EBuffType Type = EBuffType::DamageBoost;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Magnitude = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Duration = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float TickRate = 1.f;
    float TimeRemaining = 0.f; float LastTickTime = 0.f;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBuffApplied, EBuffType, Type);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBuffExpired, EBuffType, Type);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UBuffDebuffComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UBuffDebuffComponent();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TArray<FBuff> ActiveBuffs;
    UPROPERTY(BlueprintAssignable) FOnBuffApplied OnBuffApplied;
    UPROPERTY(BlueprintAssignable) FOnBuffExpired OnBuffExpired;
    UFUNCTION(BlueprintCallable) void ApplyBuff(FBuff Buff);
    UFUNCTION(BlueprintCallable) void RemoveBuff(EBuffType Type);
    UFUNCTION(BlueprintCallable) void ClearAll();
    UFUNCTION(BlueprintPure) bool HasBuff(EBuffType Type) const;
    UFUNCTION(BlueprintPure) float GetBuffMagnitude(EBuffType Type) const;
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["camera_manager"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CameraManagerComponent.generated.h"
UENUM(BlueprintType) enum class ECameraMode : uint8 { ThirdPerson, FirstPerson, TopDown, Isometric, Cinematic };
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCameraManagerComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UCameraManagerComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") ECameraMode CurrentMode = ECameraMode::ThirdPerson;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") float ThirdPersonDistance = 400.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") float SmoothSpeed = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") float FOV = 90.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") bool bInvertY = false;
    UFUNCTION(BlueprintCallable) void SwitchMode(ECameraMode NewMode);
    UFUNCTION(BlueprintCallable) void ShakeCamera(float Intensity, float Duration);
    UFUNCTION(BlueprintCallable) void ZoomIn(float Amount);
    UFUNCTION(BlueprintCallable) void ZoomOut(float Amount);
    UFUNCTION(BlueprintCallable) void SetFOV(float NewFOV);
protected:
    virtual void BeginPlay() override;
private:
    class UCameraComponent* Camera;
    class USpringArmComponent* SpringArm;
    float ShakeDuration = 0.f; float ShakeIntensity = 0.f;
};"""

UNREAL_GAME_TEMPLATES["patrol_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PatrolComponent.generated.h"
UENUM(BlueprintType) enum class EPatrolMode : uint8 { Loop, PingPong, Random, OneShot };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWaypointReached, int32, WaypointIndex);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UPatrolComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UPatrolComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Patrol") TArray<AActor*> Waypoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Patrol") EPatrolMode PatrolMode = EPatrolMode::Loop;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Patrol") float MoveSpeed = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Patrol") float WaitTime = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Patrol") float AcceptanceRadius = 50.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Patrol") int32 CurrentWaypointIndex = 0;
    UPROPERTY(BlueprintAssignable) FOnWaypointReached OnWaypointReached;
    UFUNCTION(BlueprintCallable) void StartPatrol();
    UFUNCTION(BlueprintCallable) void StopPatrol();
    UFUNCTION(BlueprintCallable) void ResumePatrol();
    UFUNCTION(BlueprintPure) FVector GetCurrentTargetLocation() const;
    UFUNCTION(BlueprintPure) bool HasWaypoints() const { return Waypoints.Num() > 0; }
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
private:
    bool bIsPatrolling = false;
    bool bIsWaiting = false;
    int32 PatrolDirection = 1;
    FTimerHandle WaitTimer;
    void AdvanceWaypoint();
    void OnWaitComplete();
};"""

UNREAL_GAME_TEMPLATES["interaction_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InteractionSystemComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnInteract, AActor*, Target);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFocus, AActor*, Target);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UInteractionSystemComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UInteractionSystemComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Interaction") float InteractRange = 250.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Interaction") float SweepRadius = 30.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Interaction") AActor* FocusedActor = nullptr;
    UPROPERTY(BlueprintAssignable) FOnInteract OnInteract;
    UPROPERTY(BlueprintAssignable) FOnFocus    OnFocus;
    UFUNCTION(BlueprintCallable) void TryInteract();
    UFUNCTION(BlueprintCallable) void UpdateFocus();
    UFUNCTION(BlueprintPure) bool HasFocus() const { return IsValid(FocusedActor); }
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
};"""

UNREAL_GAME_TEMPLATES["noise_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NoiseEmitterComponent.generated.h"
UENUM(BlueprintType) enum class ENoiseType : uint8 { Footstep, Gunshot, Explosion, Ambient, Voice };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnNoiseMade, AActor*, Source, ENoiseType, Type, float, Volume);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UNoiseEmitterComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UNoiseEmitterComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Noise") float FootstepVolume = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Noise") float GunshotVolume  = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Noise") bool bSilenced = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Noise") float SilencerMultiplier = 0.1f;
    UPROPERTY(BlueprintAssignable) FOnNoiseMade OnNoiseMade;
    UFUNCTION(BlueprintCallable) void MakeNoise(ENoiseType Type, float Volume);
    UFUNCTION(BlueprintCallable) void MakeFootstep();
    UFUNCTION(BlueprintCallable) void MakeGunshot();
    UFUNCTION(BlueprintCallable) void AlertNearbyAI(float Volume);
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES["lock_on_target"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "LockOnComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLockOn, AActor*, Target);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnLockOff);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API ULockOnComponent : public UActorComponent {
    GENERATED_BODY()
public:
    ULockOnComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="LockOn") float LockOnRange = 1500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="LockOn") float LockOnFOV   = 60.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="LockOn") float RotationSpeed = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="LockOn") FName EnemyTag = "Enemy";
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) AActor* LockedTarget = nullptr;
    UPROPERTY(BlueprintAssignable) FOnLockOn  OnLockOn;
    UPROPERTY(BlueprintAssignable) FOnLockOff OnLockOff;
    UFUNCTION(BlueprintCallable) void ToggleLockOn();
    UFUNCTION(BlueprintCallable) void SwitchTarget(bool bNext);
    UFUNCTION(BlueprintCallable) void ClearLock();
    UFUNCTION(BlueprintPure) bool IsLockedOn() const { return IsValid(LockedTarget); }
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
private:
    TArray<AActor*> ValidTargets;
    int32 TargetIndex = 0;
    void FindTargets();
    void RotateToTarget(float DeltaTime);
};"""

UNREAL_GAME_TEMPLATES["ragdoll_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "RagdollComponent.generated.h"
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API URagdollComponent : public UActorComponent {
    GENERATED_BODY()
public:
    URagdollComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ragdoll") float RagdollDelay = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ragdoll") float DestroyDelay = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ragdoll") bool bDestroyAfterRagdoll = true;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsRagdoll = false;
    UFUNCTION(BlueprintCallable) void EnableRagdoll();
    UFUNCTION(BlueprintCallable) void EnableRagdollWithImpulse(FVector Impulse, FName BoneName);
    UFUNCTION(BlueprintCallable) void DisableRagdoll();
protected:
    virtual void BeginPlay() override;
private:
    class USkeletalMeshComponent* Mesh;
    FTimerHandle DestroyTimer;
};"""

UNREAL_GAME_TEMPLATES_CPP = {}

UNREAL_GAME_TEMPLATES_CPP["health_regeneration"] = """#include "HealthRegenComponent.h"
UHealthRegenComponent::UHealthRegenComponent() { PrimaryComponentTick.bCanEverTick = true; }
void UHealthRegenComponent::BeginPlay() { Super::BeginPlay(); CurrentHealth = MaxHealth; }
void UHealthRegenComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) {
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!bRegenEnabled || CurrentHealth <= 0.f || CurrentHealth >= MaxHealth) return;
    TimeSinceDamage += DeltaTime;
    if (TimeSinceDamage >= RegenDelay) { CurrentHealth = FMath::Min(CurrentHealth + RegenRate * DeltaTime, MaxHealth); }
}
void UHealthRegenComponent::TakeDamage(float Damage) { CurrentHealth = FMath::Max(0.f, CurrentHealth - Damage); TimeSinceDamage = 0.f; if (CurrentHealth <= 0.f) Die(); }
void UHealthRegenComponent::Heal(float Amount) { CurrentHealth = FMath::Min(CurrentHealth + Amount, MaxHealth); }
float UHealthRegenComponent::GetHealthPercent() const { return MaxHealth > 0.f ? CurrentHealth / MaxHealth : 0.f; }
void UHealthRegenComponent::Die() { if (GetOwner()) GetOwner()->Destroy(); }"""

UNREAL_GAME_TEMPLATES_CPP["armor_system"] = """#include "ArmorComponent.h"
UArmorComponent::UArmorComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UArmorComponent::BeginPlay() { Super::BeginPlay(); CurrentArmor = MaxArmor; }
float UArmorComponent::AbsorbDamage(float IncomingDamage) {
    if (CurrentArmor <= 0.f) return IncomingDamage;
    float Absorbed = IncomingDamage * DamageReduction;
    CurrentArmor = FMath::Max(0.f, CurrentArmor - Absorbed);
    return IncomingDamage - Absorbed;
}
void UArmorComponent::RepairArmor(float Amount) { CurrentArmor = FMath::Min(CurrentArmor + Amount, MaxArmor); }
float UArmorComponent::GetArmorPercent() const { return MaxArmor > 0.f ? CurrentArmor / MaxArmor : 0.f; }"""

UNREAL_GAME_TEMPLATES_CPP["projectile_actor"] = """#include "ProjectileActor.h"
#include "Kismet/GameplayStatics.h"
AProjectileActor::AProjectileActor() {
    CollisionComp = CreateDefaultSubobject<USphereComponent>(TEXT("SphereComp"));
    CollisionComp->InitSphereRadius(5.f);
    CollisionComp->SetCollisionProfileName("Projectile");
    RootComponent = CollisionComp;
    ProjectileMovement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("ProjectileMovement"));
    ProjectileMovement->InitialSpeed = 3000.f;
    ProjectileMovement->MaxSpeed = 3000.f;
    ProjectileMovement->bRotationFollowsVelocity = true;
    InitialLifeSpan = Lifetime;
}
void AProjectileActor::BeginPlay() {
    Super::BeginPlay();
    CollisionComp->OnComponentHit.AddDynamic(this, &AProjectileActor::OnHit);
    CollisionComp->OnComponentBeginOverlap.AddDynamic(this, &AProjectileActor::OnOverlap);
}
void AProjectileActor::SetVelocity(FVector Velocity) { if (ProjectileMovement) ProjectileMovement->Velocity = Velocity; }
void AProjectileActor::OnHit(UPrimitiveComponent* HitComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit) {
    if (OtherActor && OtherActor != this) {
        UGameplayStatics::ApplyDamage(OtherActor, Damage, GetInstigatorController(), this, nullptr);
        if (ExplosionRadius > 0.f) UGameplayStatics::ApplyRadialDamage(GetWorld(), Damage, GetActorLocation(), ExplosionRadius, nullptr, {}, this);
    }
    Destroy();
}
void AProjectileActor::OnOverlap(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult) {
    if (OtherActor && OtherActor != this) { UGameplayStatics::ApplyDamage(OtherActor, Damage, GetInstigatorController(), this, nullptr); Destroy(); }
}"""

UNREAL_GAME_TEMPLATES_CPP["enemy_spawner"] = """#include "EnemySpawnerActor.h"
AEnemySpawnerActor::AEnemySpawnerActor() { PrimaryActorTick.bCanEverTick = false; }
void AEnemySpawnerActor::BeginPlay() { Super::BeginPlay(); StartSpawning(); }
void AEnemySpawnerActor::StartSpawning() { GetWorldTimerManager().SetTimer(SpawnTimer, this, &AEnemySpawnerActor::SpawnEnemy, SpawnInterval, true); }
void AEnemySpawnerActor::StopSpawning() { GetWorldTimerManager().ClearTimer(SpawnTimer); }
void AEnemySpawnerActor::OnEnemyKilled() { EnemiesAlive = FMath::Max(0, EnemiesAlive - 1); }
void AEnemySpawnerActor::SpawnEnemy() {
    if (!CanSpawn()) return;
    FVector RandOffset(FMath::FRandRange(-SpawnRadius, SpawnRadius), FMath::FRandRange(-SpawnRadius, SpawnRadius), 0.f);
    AActor* Spawned = GetWorld()->SpawnActor<AActor>(EnemyClass, GetActorLocation() + RandOffset, GetActorRotation());
    if (IsValid(Spawned)) { EnemiesAlive++; OnEnemySpawned.Broadcast(Spawned); }
}"""

UNREAL_GAME_TEMPLATES_CPP["player_character"] = """#include "PlayerCharacterBase.h"
#include "GameFramework/CharacterMovementComponent.h"
APlayerCharacterBase::APlayerCharacterBase() {
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 400.f;
    CameraBoom->bUsePawnControlRotation = true;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
}
void APlayerCharacterBase::BeginPlay() { Super::BeginPlay(); CurrentHealth = MaxHealth; }
void APlayerCharacterBase::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) {
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxis("MoveForward", this, &APlayerCharacterBase::MoveForward);
    PlayerInputComponent->BindAxis("MoveRight",   this, &APlayerCharacterBase::MoveRight);
    PlayerInputComponent->BindAxis("Turn",        this, &APawn::AddControllerYawInput);
    PlayerInputComponent->BindAxis("LookUp",      this, &APawn::AddControllerPitchInput);
    PlayerInputComponent->BindAction("Jump",   IE_Pressed, this, &ACharacter::Jump);
    PlayerInputComponent->BindAction("Sprint", IE_Pressed,  this, &APlayerCharacterBase::Sprint, true);
    PlayerInputComponent->BindAction("Sprint", IE_Released, this, &APlayerCharacterBase::Sprint, false);
    PlayerInputComponent->BindAction("Fire",   IE_Pressed,  this, &APlayerCharacterBase::Fire);
}
void APlayerCharacterBase::MoveForward(float Value) { if (Value != 0.f) AddMovementInput(GetActorForwardVector(), Value); }
void APlayerCharacterBase::MoveRight(float Value)   { if (Value != 0.f) AddMovementInput(GetActorRightVector(), Value); }
void APlayerCharacterBase::Sprint(bool bSprint) { GetCharacterMovement()->MaxWalkSpeed = bSprint ? SprintSpeed : WalkSpeed; }
void APlayerCharacterBase::Fire() {
    if (!IsValid(ProjectileClass) || GetWorld()->GetTimeSeconds() - LastFireTime < FireCooldown) return;
    LastFireTime = GetWorld()->GetTimeSeconds();
    FVector SpawnLoc = GetActorLocation() + GetActorForwardVector() * 100.f;
    GetWorld()->SpawnActor<AActor>(ProjectileClass, SpawnLoc, GetActorRotation());
}
void APlayerCharacterBase::TakeDamage(float Damage) { CurrentHealth = FMath::Max(0.f, CurrentHealth - Damage); if (CurrentHealth <= 0.f) Die(); }
void APlayerCharacterBase::Heal(float Amount) { CurrentHealth = FMath::Min(CurrentHealth + Amount, MaxHealth); }
void APlayerCharacterBase::Die() { GetCharacterMovement()->DisableMovement(); DisableInput(Cast<APlayerController>(GetController())); SetLifeSpan(2.f); }"""

UNREAL_GAME_TEMPLATES_CPP["enemy_character"] = """#include "EnemyCharacterBase.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
AEnemyCharacterBase::AEnemyCharacterBase() { PrimaryActorTick.bCanEverTick = true; GetCharacterMovement()->MaxWalkSpeed = MoveSpeed; }
void AEnemyCharacterBase::BeginPlay() { Super::BeginPlay(); CurrentHealth = MaxHealth; Target = UGameplayStatics::GetPlayerPawn(GetWorld(), 0); }
void AEnemyCharacterBase::Tick(float DeltaTime) { Super::Tick(DeltaTime); if (IsAlive()) UpdateAI(DeltaTime); }
void AEnemyCharacterBase::UpdateAI(float DeltaTime) {
    if (!IsValid(Target)) return;
    float Dist = GetDistanceTo(Target);
    if (Dist <= AttackRange) { State = EEnemyState::Attack; AttackTarget(); }
    else if (Dist <= DetectionRadius) { State = EEnemyState::Chase; AddMovementInput((Target->GetActorLocation() - GetActorLocation()).GetSafeNormal()); }
    else { State = EEnemyState::Idle; }
}
void AEnemyCharacterBase::AttackTarget() { if (IsValid(Target)) UGameplayStatics::ApplyDamage(Target, AttackDamage, GetController(), this, nullptr); }
void AEnemyCharacterBase::TakeDamage(float Damage) { CurrentHealth = FMath::Max(0.f, CurrentHealth - Damage); if (CurrentHealth <= 0.f) Die(); }
void AEnemyCharacterBase::SetTarget(AActor* NewTarget) { Target = NewTarget; State = EEnemyState::Chase; }
void AEnemyCharacterBase::Die() { State = EEnemyState::Dead; GetCharacterMovement()->DisableMovement(); OnEnemyDied.Broadcast(); SetLifeSpan(3.f); }"""

UNREAL_GAME_TEMPLATES_CPP["game_mode_base"] = """#include "CustomGameMode.h"
#include "Kismet/GameplayStatics.h"
ACustomGameMode::ACustomGameMode() { CurrentLives = StartingLives; }
void ACustomGameMode::BeginPlay() { Super::BeginPlay(); CurrentLives = StartingLives; CurrentScore = 0; CurrentWave = 1; }
void ACustomGameMode::AddScore(int32 Amount) { CurrentScore += Amount; }
void ACustomGameMode::OnEnemyKilled() { AddScore(ScorePerKill); }
void ACustomGameMode::OnPlayerDied() { CurrentLives = FMath::Max(0, CurrentLives - 1); if (CurrentLives <= 0) GameOver(); }
void ACustomGameMode::NextWave() { CurrentWave++; }
void ACustomGameMode::GameOver() { if (bGameOver) return; bGameOver = true; OnGameOver.Broadcast(); UGameplayStatics::SetGlobalTimeDilation(GetWorld(), 0.f); }
void ACustomGameMode::Win() { OnGameWin.Broadcast(); UGameplayStatics::SetGlobalTimeDilation(GetWorld(), 0.f); }
void ACustomGameMode::RestartGame() { bGameOver = false; UGameplayStatics::OpenLevel(GetWorld(), FName(*UGameplayStatics::GetCurrentLevelName(GetWorld()))); }"""

UNREAL_GAME_TEMPLATES_CPP["pickup_actor"] = """#include "PickupActorBase.h"
#include "Components/SphereComponent.h"
APickupActorBase::APickupActorBase() {
    PrimaryActorTick.bCanEverTick = true;
    PickupSphere = CreateDefaultSubobject<USphereComponent>(TEXT("PickupSphere"));
    PickupSphere->InitSphereRadius(50.f); PickupSphere->SetCollisionProfileName("OverlapAllDynamic");
    RootComponent = PickupSphere;
    PickupMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PickupMesh"));
    PickupMesh->SetupAttachment(RootComponent); PickupMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
void APickupActorBase::BeginPlay() { Super::BeginPlay(); PickupSphere->OnComponentBeginOverlap.AddDynamic(this, &APickupActorBase::OnOverlap); }
void APickupActorBase::Tick(float DeltaTime) { Super::Tick(DeltaTime); if (bRotate && bIsActive) AddActorLocalRotation(FRotator(0.f, RotateSpeed * DeltaTime, 0.f)); }
void APickupActorBase::OnOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32, bool, const FHitResult&) {
    if (!bIsActive || !IsValid(OtherActor) || !OtherActor->ActorHasTag("Player")) return;
    OnPickedUp.Broadcast(OtherActor, PickupType);
    if (bDestroyOnPickup) { Destroy(); } else { DisablePickup(); GetWorldTimerManager().SetTimer(FTimerHandle{}, this, &APickupActorBase::EnablePickup, RespawnTime, false); }
}
void APickupActorBase::EnablePickup()  { bIsActive = true;  SetActorHiddenInGame(false); PickupSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly); }
void APickupActorBase::DisablePickup() { bIsActive = false; SetActorHiddenInGame(true);  PickupSphere->SetCollisionEnabled(ECollisionEnabled::NoCollision); }"""

UNREAL_GAME_TEMPLATES_CPP["trigger_zone"] = """#include "TriggerZoneActor.h"
#include "Components/BoxComponent.h"
ATriggerZoneActor::ATriggerZoneActor() {
    TriggerBox = CreateDefaultSubobject<UBoxComponent>(TEXT("TriggerBox"));
    TriggerBox->SetBoxExtent(FVector(100.f)); TriggerBox->SetCollisionProfileName("OverlapAll");
    RootComponent = TriggerBox;
}
void ATriggerZoneActor::BeginPlay() {
    Super::BeginPlay();
    TriggerBox->OnComponentBeginOverlap.AddDynamic(this, &ATriggerZoneActor::OnBeginOverlap);
    TriggerBox->OnComponentEndOverlap.AddDynamic(this, &ATriggerZoneActor::OnEndOverlap);
}
void ATriggerZoneActor::OnBeginOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32, bool, const FHitResult&) {
    if (!bIsEnabled) return;
    if (bPlayerOnly && !OtherActor->ActorHasTag("Player")) return;
    if (bOneShot && bFired) return;
    bFired = true; OnTrigger.Broadcast(OtherActor, ETriggerEvent::OnEnter);
}
void ATriggerZoneActor::OnEndOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32) {
    if (!bIsEnabled) return; OnTrigger.Broadcast(OtherActor, ETriggerEvent::OnExit);
}
void ATriggerZoneActor::SetEnabled(bool bEnabled) { bIsEnabled = bEnabled; }"""

UNREAL_GAME_TEMPLATES_CPP["respawn_system"] = """#include "RespawnComponent.h"
URespawnComponent::URespawnComponent() { PrimaryComponentTick.bCanEverTick = false; }
void URespawnComponent::BeginPlay() { Super::BeginPlay(); if (GetOwner()) CheckpointLocation = GetOwner()->GetActorLocation(); }
bool URespawnComponent::CanRespawn() const { return MaxRespawns < 0 || RespawnCount < MaxRespawns; }
void URespawnComponent::Die() {
    if (!CanRespawn()) { UE_LOG(LogTemp, Warning, TEXT("No respawns left!")); return; }
    if (GetOwner()) GetOwner()->SetActorHiddenInGame(true);
    GetWorldTimerManager().SetTimer(RespawnTimer, this, &URespawnComponent::DoRespawn, RespawnDelay, false);
}
void URespawnComponent::SetCheckpoint(FVector Location) { CheckpointLocation = Location; }
void URespawnComponent::DoRespawn() {
    RespawnCount++;
    if (!GetOwner()) return;
    FVector Loc = bRespawnAtCheckpoint ? CheckpointLocation : GetOwner()->GetActorLocation();
    GetOwner()->SetActorLocation(Loc);
    GetOwner()->SetActorHiddenInGame(false);
    OnRespawn.Broadcast(Loc);
}"""

UNREAL_GAME_TEMPLATES_CPP["score_manager"] = """#include "ScoreManagerComponent.h"
#include "Kismet/GameplayStatics.h"
UScoreManagerComponent::UScoreManagerComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UScoreManagerComponent::BeginPlay() { Super::BeginPlay(); LoadHighScore(); }
void UScoreManagerComponent::AddScore(int32 Amount) {
    int32 Delta = Amount * ScoreMultiplier;
    CurrentScore += Delta;
    OnScoreChanged.Broadcast(CurrentScore, Delta);
    if (CurrentScore > HighScore) { HighScore = CurrentScore; OnHighScore.Broadcast(HighScore); SaveHighScore(); }
}
void UScoreManagerComponent::SetMultiplier(int32 Multiplier) {
    ScoreMultiplier = Multiplier;
    GetWorldTimerManager().SetTimer(MultiplierTimer, this, &UScoreManagerComponent::ResetMultiplier, MultiplierDuration, false);
}
void UScoreManagerComponent::ResetMultiplier() { ScoreMultiplier = 1; }
void UScoreManagerComponent::ResetScore() { CurrentScore = 0; OnScoreChanged.Broadcast(0, 0); }
void UScoreManagerComponent::SaveHighScore() { UGameplayStatics::SaveGameToSlot(nullptr, "HighScore", 0); }
void UScoreManagerComponent::LoadHighScore() { HighScore = 0; }"""

UNREAL_GAME_TEMPLATES_CPP["ammo_system"] = """#include "AmmoComponent.h"
UAmmoComponent::UAmmoComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UAmmoComponent::BeginPlay() { Super::BeginPlay(); }
bool UAmmoComponent::TryShoot() {
    if (!CanShoot()) { if (NeedsReload()) StartReload(); return false; }
    CurrentMagazine--; OnAmmoChanged.Broadcast(CurrentAmmoType, CurrentMagazine);
    return true;
}
void UAmmoComponent::StartReload() {
    if (bIsReloading || ReserveAmmo <= 0 || CurrentMagazine >= MagazineSize) return;
    bIsReloading = true;
    GetWorldTimerManager().SetTimer(ReloadTimer, this, &UAmmoComponent::FinishReload, ReloadTime, false);
}
void UAmmoComponent::FinishReload() {
    int32 Needed = MagazineSize - CurrentMagazine;
    int32 Added  = FMath::Min(Needed, ReserveAmmo);
    CurrentMagazine += Added; ReserveAmmo -= Added; bIsReloading = false;
    OnReloadComplete.Broadcast(CurrentAmmoType); OnAmmoChanged.Broadcast(CurrentAmmoType, CurrentMagazine);
}
void UAmmoComponent::AddAmmo(EAmmoType Type, int32 Amount) { if (Type == CurrentAmmoType) { ReserveAmmo += Amount; OnAmmoChanged.Broadcast(Type, ReserveAmmo); } }"""

UNREAL_GAME_TEMPLATES_CPP["door_system"] = """#include "DoorActor.h"
ADoorActor::ADoorActor() {
    PrimaryActorTick.bCanEverTick = true;
    DoorMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DoorMesh"));
    RootComponent = DoorMesh;
}
void ADoorActor::BeginPlay() { Super::BeginPlay(); State = bStartLocked ? EDoorState::Locked : EDoorState::Closed; TargetRotation = GetActorRotation(); }
void ADoorActor::Tick(float DeltaTime) {
    Super::Tick(DeltaTime);
    if (State == EDoorState::Opening || State == EDoorState::Closing) {
        FRotator Current = GetActorRotation();
        FRotator New = FMath::RInterpTo(Current, TargetRotation, DeltaTime, OpenSpeed);
        SetActorRotation(New);
        if (Current.Equals(TargetRotation, 0.5f)) {
            State = (State == EDoorState::Opening) ? EDoorState::Open : EDoorState::Closed;
            OnDoorStateChanged.Broadcast(State);
            if (State == EDoorState::Open && bAutoClose) GetWorldTimerManager().SetTimer(AutoCloseTimer, this, &ADoorActor::Close, AutoCloseDelay, false);
        }
    }
}
void ADoorActor::Open()   { if (State == EDoorState::Locked || State == EDoorState::Open) return; State = EDoorState::Opening; TargetRotation = GetActorRotation() + FRotator(0.f, OpenAngle, 0.f); OnDoorStateChanged.Broadcast(State); }
void ADoorActor::Close()  { if (State == EDoorState::Closed) return; State = EDoorState::Closing; TargetRotation = FRotator::ZeroRotator; OnDoorStateChanged.Broadcast(State); }
void ADoorActor::Lock()   { Close(); State = EDoorState::Locked; OnDoorStateChanged.Broadcast(State); }
void ADoorActor::Unlock() { State = EDoorState::Closed; OnDoorStateChanged.Broadcast(State); }
void ADoorActor::Toggle() { (IsOpen() || State == EDoorState::Opening) ? Close() : Open(); }"""

UNREAL_GAME_TEMPLATES_CPP["level_manager"] = """#include "LevelManagerComponent.h"
#include "Kismet/GameplayStatics.h"
ULevelManagerComponent::ULevelManagerComponent() { PrimaryComponentTick.bCanEverTick = false; }
void ULevelManagerComponent::BeginPlay() { Super::BeginPlay(); }
void ULevelManagerComponent::LoadLevel(FString LevelName) { OnLevelLoad.Broadcast(LevelName); UGameplayStatics::OpenLevel(GetWorld(), FName(*LevelName)); }
void ULevelManagerComponent::LoadLevelByIndex(int32 Index) { if (LevelNames.IsValidIndex(Index)) { CurrentLevelIndex = Index; LoadLevel(LevelNames[Index]); } }
void ULevelManagerComponent::LoadNextLevel() { if (HasNextLevel()) LoadLevelByIndex(CurrentLevelIndex + 1); }
void ULevelManagerComponent::ReloadCurrentLevel() { LoadLevel(UGameplayStatics::GetCurrentLevelName(GetWorld())); }
void ULevelManagerComponent::LoadMainMenu() { LoadLevel(TEXT("MainMenu")); }"""

UNREAL_GAME_TEMPLATES_CPP["buff_debuff"] = """#include "BuffDebuffComponent.h"
UBuffDebuffComponent::UBuffDebuffComponent() { PrimaryComponentTick.bCanEverTick = true; }
void UBuffDebuffComponent::BeginPlay() { Super::BeginPlay(); }
void UBuffDebuffComponent::TickComponent(float DeltaTime, ELevelTick T, FActorComponentTickFunction* F) {
    Super::TickComponent(DeltaTime, T, F);
    for (int32 i = ActiveBuffs.Num() - 1; i >= 0; i--) {
        ActiveBuffs[i].TimeRemaining -= DeltaTime;
        if (ActiveBuffs[i].TimeRemaining <= 0.f) { OnBuffExpired.Broadcast(ActiveBuffs[i].Type); ActiveBuffs.RemoveAt(i); }
    }
}
void UBuffDebuffComponent::ApplyBuff(FBuff Buff) {
    for (FBuff& B : ActiveBuffs) { if (B.Type == Buff.Type) { B = Buff; B.TimeRemaining = Buff.Duration; OnBuffApplied.Broadcast(Buff.Type); return; } }
    Buff.TimeRemaining = Buff.Duration; ActiveBuffs.Add(Buff); OnBuffApplied.Broadcast(Buff.Type);
}
void UBuffDebuffComponent::RemoveBuff(EBuffType Type) { ActiveBuffs.RemoveAll([Type](const FBuff& B){ return B.Type == Type; }); OnBuffExpired.Broadcast(Type); }
void UBuffDebuffComponent::ClearAll() { ActiveBuffs.Empty(); }
bool UBuffDebuffComponent::HasBuff(EBuffType Type) const { return ActiveBuffs.ContainsByPredicate([Type](const FBuff& B){ return B.Type == Type; }); }
float UBuffDebuffComponent::GetBuffMagnitude(EBuffType Type) const { for (auto& B : ActiveBuffs) if (B.Type == Type) return B.Magnitude; return 1.f; }"""

UNREAL_GAME_TEMPLATES_CPP["camera_manager"] = """#include "CameraManagerComponent.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
UCameraManagerComponent::UCameraManagerComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UCameraManagerComponent::BeginPlay() {
    Super::BeginPlay();
    if (GetOwner()) {
        Camera    = GetOwner()->FindComponentByClass<UCameraComponent>();
        SpringArm = GetOwner()->FindComponentByClass<USpringArmComponent>();
    }
}
void UCameraManagerComponent::SwitchMode(ECameraMode NewMode) {
    CurrentMode = NewMode;
    if (!SpringArm) return;
    switch (NewMode) {
        case ECameraMode::ThirdPerson:  SpringArm->TargetArmLength = ThirdPersonDistance; break;
        case ECameraMode::FirstPerson:  SpringArm->TargetArmLength = 0.f; break;
        case ECameraMode::TopDown:      SpringArm->SetRelativeRotation(FRotator(-90.f,0.f,0.f)); SpringArm->TargetArmLength = 1200.f; break;
        case ECameraMode::Isometric:    SpringArm->SetRelativeRotation(FRotator(-45.f,45.f,0.f)); SpringArm->TargetArmLength = 1000.f; break;
        default: break;
    }
}
void UCameraManagerComponent::ShakeCamera(float Intensity, float Duration) { ShakeIntensity = Intensity; ShakeDuration = Duration; }
void UCameraManagerComponent::ZoomIn(float Amount)  { if (SpringArm) SpringArm->TargetArmLength = FMath::Max(100.f, SpringArm->TargetArmLength - Amount); }
void UCameraManagerComponent::ZoomOut(float Amount) { if (SpringArm) SpringArm->TargetArmLength = FMath::Min(2000.f, SpringArm->TargetArmLength + Amount); }
void UCameraManagerComponent::SetFOV(float NewFOV)  { FOV = NewFOV; if (Camera) Camera->SetFieldOfView(NewFOV); }"""

UNREAL_GAME_TEMPLATES_CPP["patrol_system"] = """#include "PatrolComponent.h"
UPatrolComponent::UPatrolComponent() { PrimaryComponentTick.bCanEverTick = true; }
void UPatrolComponent::BeginPlay() { Super::BeginPlay(); if (HasWaypoints()) StartPatrol(); }
void UPatrolComponent::TickComponent(float DeltaTime, ELevelTick T, FActorComponentTickFunction* F) {
    Super::TickComponent(DeltaTime, T, F);
    if (!bIsPatrolling || bIsWaiting || !HasWaypoints()) return;
    FVector Target = GetCurrentTargetLocation();
    FVector Current = GetOwner()->GetActorLocation();
    float Dist = FVector::Dist(Current, Target);
    if (Dist <= AcceptanceRadius) { OnWaypointReached.Broadcast(CurrentWaypointIndex); bIsWaiting = true; GetWorldTimerManager().SetTimer(WaitTimer, this, &UPatrolComponent::OnWaitComplete, WaitTime, false); }
    else { FVector Dir = (Target - Current).GetSafeNormal(); GetOwner()->SetActorLocation(Current + Dir * MoveSpeed * DeltaTime); GetOwner()->SetActorRotation(Dir.Rotation()); }
}
void UPatrolComponent::StartPatrol()  { bIsPatrolling = true; }
void UPatrolComponent::StopPatrol()   { bIsPatrolling = false; GetWorldTimerManager().ClearTimer(WaitTimer); }
void UPatrolComponent::ResumePatrol() { bIsPatrolling = true; }
FVector UPatrolComponent::GetCurrentTargetLocation() const { return Waypoints.IsValidIndex(CurrentWaypointIndex) && IsValid(Waypoints[CurrentWaypointIndex]) ? Waypoints[CurrentWaypointIndex]->GetActorLocation() : GetOwner()->GetActorLocation(); }
void UPatrolComponent::OnWaitComplete() { bIsWaiting = false; AdvanceWaypoint(); }
void UPatrolComponent::AdvanceWaypoint() {
    if (PatrolMode == EPatrolMode::Random) { CurrentWaypointIndex = FMath::RandRange(0, Waypoints.Num()-1); return; }
    if (PatrolMode == EPatrolMode::PingPong) {
        CurrentWaypointIndex += PatrolDirection;
        if (CurrentWaypointIndex >= Waypoints.Num()-1 || CurrentWaypointIndex <= 0) PatrolDirection *= -1;
    } else { CurrentWaypointIndex = (CurrentWaypointIndex + 1) % Waypoints.Num(); }
}"""

UNREAL_GAME_TEMPLATES_CPP["interaction_system"] = """#include "InteractionSystemComponent.h"
#include "DrawDebugHelpers.h"
UInteractionSystemComponent::UInteractionSystemComponent() { PrimaryComponentTick.bCanEverTick = true; }
void UInteractionSystemComponent::BeginPlay() { Super::BeginPlay(); }
void UInteractionSystemComponent::TickComponent(float DeltaTime, ELevelTick T, FActorComponentTickFunction* F) { Super::TickComponent(DeltaTime, T, F); UpdateFocus(); }
void UInteractionSystemComponent::UpdateFocus() {
    if (!GetOwner()) return;
    FVector Start = GetOwner()->GetActorLocation();
    FVector End   = Start + GetOwner()->GetActorForwardVector() * InteractRange;
    FHitResult Hit;
    FCollisionQueryParams Params; Params.AddIgnoredActor(GetOwner());
    bool bHit = GetWorld()->SweepSingleByChannel(Hit, Start, End, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(SweepRadius), Params);
    AActor* NewFocus = bHit ? Hit.GetActor() : nullptr;
    if (NewFocus != FocusedActor) { FocusedActor = NewFocus; if (IsValid(FocusedActor)) OnFocus.Broadcast(FocusedActor); }
}
void UInteractionSystemComponent::TryInteract() { if (IsValid(FocusedActor)) { FocusedActor->NotifyActorOnClicked(); OnInteract.Broadcast(FocusedActor); } }"""

UNREAL_GAME_TEMPLATES_CPP["noise_system"] = """#include "NoiseEmitterComponent.h"
#include "Kismet/GameplayStatics.h"
UNoiseEmitterComponent::UNoiseEmitterComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UNoiseEmitterComponent::BeginPlay() { Super::BeginPlay(); }
void UNoiseEmitterComponent::MakeNoise(ENoiseType Type, float Volume) {
    float FinalVolume = bSilenced ? Volume * SilencerMultiplier : Volume;
    OnNoiseMade.Broadcast(GetOwner(), Type, FinalVolume);
    AlertNearbyAI(FinalVolume);
}
void UNoiseEmitterComponent::MakeFootstep() { MakeNoise(ENoiseType::Footstep, FootstepVolume); }
void UNoiseEmitterComponent::MakeGunshot()  { MakeNoise(ENoiseType::Gunshot, GunshotVolume); }
void UNoiseEmitterComponent::AlertNearbyAI(float Volume) {
    TArray<AActor*> NearbyActors;
    float Radius = Volume * 2000.f;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), NearbyActors);
    for (AActor* Actor : NearbyActors) {
        if (!IsValid(Actor) || Actor == GetOwner()) continue;
        if (FVector::Dist(GetOwner()->GetActorLocation(), Actor->GetActorLocation()) <= Radius)
            Actor->NotifyActorBeginOverlap(GetOwner());
    }
}"""

UNREAL_GAME_TEMPLATES_CPP["lock_on_target"] = """#include "LockOnComponent.h"
#include "Kismet/GameplayStatics.h"
ULockOnComponent::ULockOnComponent() { PrimaryComponentTick.bCanEverTick = true; }
void ULockOnComponent::BeginPlay() { Super::BeginPlay(); }
void ULockOnComponent::TickComponent(float DeltaTime, ELevelTick T, FActorComponentTickFunction* F) {
    Super::TickComponent(DeltaTime, T, F);
    if (IsLockedOn()) { if (GetDistanceTo(LockedTarget) > LockOnRange * 1.2f) ClearLock(); else RotateToTarget(DeltaTime); }
}
void ULockOnComponent::FindTargets() {
    ValidTargets.Empty();
    TArray<AActor*> All; UGameplayStatics::GetAllActorsWithTag(GetWorld(), EnemyTag, All);
    for (AActor* A : All) { if (IsValid(A) && FVector::Dist(GetOwner()->GetActorLocation(), A->GetActorLocation()) <= LockOnRange) ValidTargets.Add(A); }
    ValidTargets.Sort([this](const AActor& A, const AActor& B){ return FVector::Dist(GetOwner()->GetActorLocation(), A.GetActorLocation()) < FVector::Dist(GetOwner()->GetActorLocation(), B.GetActorLocation()); });
}
void ULockOnComponent::ToggleLockOn() { if (IsLockedOn()) { ClearLock(); } else { FindTargets(); if (ValidTargets.Num() > 0) { TargetIndex = 0; LockedTarget = ValidTargets[0]; OnLockOn.Broadcast(LockedTarget); } } }
void ULockOnComponent::SwitchTarget(bool bNext) { FindTargets(); if (ValidTargets.Num() == 0) return; TargetIndex = bNext ? (TargetIndex + 1) % ValidTargets.Num() : (TargetIndex - 1 + ValidTargets.Num()) % ValidTargets.Num(); LockedTarget = ValidTargets[TargetIndex]; OnLockOn.Broadcast(LockedTarget); }
void ULockOnComponent::ClearLock() { LockedTarget = nullptr; OnLockOff.Broadcast(); }
void ULockOnComponent::RotateToTarget(float DeltaTime) { if (!GetOwner() || !IsValid(LockedTarget)) return; FVector Dir = (LockedTarget->GetActorLocation() - GetOwner()->GetActorLocation()).GetSafeNormal(); FRotator Target = Dir.Rotation(); GetOwner()->SetActorRotation(FMath::RInterpTo(GetOwner()->GetActorRotation(), Target, DeltaTime, RotationSpeed)); }"""

UNREAL_GAME_TEMPLATES_CPP["ragdoll_system"] = """#include "RagdollComponent.h"
#include "Components/SkeletalMeshComponent.h"
URagdollComponent::URagdollComponent() { PrimaryComponentTick.bCanEverTick = false; }
void URagdollComponent::BeginPlay() { Super::BeginPlay(); if (GetOwner()) Mesh = GetOwner()->FindComponentByClass<USkeletalMeshComponent>(); }
void URagdollComponent::EnableRagdoll() {
    if (!Mesh || bIsRagdoll) return; bIsRagdoll = true;
    Mesh->SetSimulatePhysics(true); Mesh->SetCollisionProfileName("Ragdoll");
    if (bDestroyAfterRagdoll) GetWorldTimerManager().SetTimer(DestroyTimer, [this](){ if (GetOwner()) GetOwner()->Destroy(); }, DestroyDelay, false);
}
void URagdollComponent::EnableRagdollWithImpulse(FVector Impulse, FName BoneName) {
    EnableRagdoll();
    if (Mesh) Mesh->AddImpulse(Impulse, BoneName, true);
}
void URagdollComponent::DisableRagdoll() { if (!Mesh || !bIsRagdoll) return; bIsRagdoll = false; Mesh->SetSimulatePhysics(false); }"""


UNREAL_GAME_KEYWORDS.update({
    "health_regeneration": ["health regen", "regeneration", "regen health", "auto heal", "hp regen"],
    "armor_system": ["armor", "armour", "shield absorb", "damage reduction", "defense"],
    "projectile_actor": ["projectile", "bullet actor", "missile", "arrow actor", "shot"],
    "enemy_spawner": ["enemy spawner", "spawn enemy", "wave spawn", "spawner actor"],
    "player_character": ["player character", "player pawn", "hero character", "protagonist"],
    "enemy_character": ["enemy character", "ai character", "enemy pawn", "foe character"],
    "game_mode_base": ["game mode", "gamemode", "score", "wave", "game manager", "gm"],
    "pickup_actor": ["pickup", "item pickup", "collectible actor", "loot pickup", "drop"],
    "trigger_zone": ["trigger", "trigger zone", "trigger volume", "area trigger", "proximity"],
    "respawn_system": ["respawn", "respawn point", "revive", "spawn on death"],
    "score_manager": ["score", "points", "high score", "score manager", "combo score"],
    "ammo_system": ["ammo", "ammunition", "magazine", "reload", "bullets"],
    "door_system": ["door", "gate", "sliding door", "auto door", "lock door"],
    "level_manager": ["level", "load level", "scene change", "level transition", "next level"],
    "buff_debuff": ["buff", "debuff", "power up effect", "status boost", "temporary boost"],
    "camera_manager": ["camera mode", "camera switch", "fov", "zoom camera", "first third person"],
    "patrol_system": ["patrol", "patrol path", "waypoint walk", "guard patrol", "enemy patrol"],
    "interaction_system": ["interaction system", "interact range", "focus", "highlight interact"],
    "noise_system": ["noise", "sound alert", "footstep noise", "gunshot alert", "stealth sound"],
    "lock_on_target": ["lock on", "target lock", "auto aim", "soft lock", "target system"],
    "ragdoll_system": ["ragdoll", "physics death", "rag doll", "death physics", "body physics"],
})

# ── BATCH 2: MORE COMPREHENSIVE TEMPLATES ──────────────────────

UNREAL_GAME_TEMPLATES["melee_combat"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MeleeCombatComponent.generated.h"
UENUM(BlueprintType) enum class EMeleeAttack : uint8 { Light, Heavy, Uppercut, Spin, Finisher };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnMeleeHit, AActor*, HitActor, float, Damage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAttackStart, EMeleeAttack, AttackType);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UMeleeCombatComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UMeleeCombatComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float LightDamage   = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float HeavyDamage   = 50.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float AttackRange   = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float AttackAngle   = 60.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float LightCooldown = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Melee") float HeavyCooldown = 1.2f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsAttacking = false;
    UPROPERTY(BlueprintAssignable) FOnMeleeHit   OnMeleeHit;
    UPROPERTY(BlueprintAssignable) FOnAttackStart OnAttackStart;
    UFUNCTION(BlueprintCallable) void LightAttack();
    UFUNCTION(BlueprintCallable) void HeavyAttack();
    UFUNCTION(BlueprintCallable) void EndAttack();
    UFUNCTION(BlueprintCallable) void EnableHitbox(bool bEnable);
    UFUNCTION(BlueprintPure) bool CanAttack() const;
protected:
    virtual void BeginPlay() override;
private:
    float LastAttackTime = -999.f;
    float CurrentCooldown = 0.4f;
    void PerformAttack(EMeleeAttack Type, float Damage, float Cooldown);
    void DoHitScan();
    FTimerHandle AttackTimer;
};"""

UNREAL_GAME_TEMPLATES_CPP["melee_combat"] = """#include "MeleeCombatComponent.h"
#include "Kismet/GameplayStatics.h"
#include "DrawDebugHelpers.h"
UMeleeCombatComponent::UMeleeCombatComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UMeleeCombatComponent::BeginPlay() { Super::BeginPlay(); }
bool UMeleeCombatComponent::CanAttack() const { return !bIsAttacking && GetWorld()->GetTimeSeconds() - LastAttackTime >= CurrentCooldown; }
void UMeleeCombatComponent::LightAttack() { if (CanAttack()) PerformAttack(EMeleeAttack::Light, LightDamage, LightCooldown); }
void UMeleeCombatComponent::HeavyAttack() { if (CanAttack()) PerformAttack(EMeleeAttack::Heavy, HeavyDamage, HeavyCooldown); }
void UMeleeCombatComponent::PerformAttack(EMeleeAttack Type, float Damage, float Cooldown) {
    bIsAttacking = true; CurrentCooldown = Cooldown; LastAttackTime = GetWorld()->GetTimeSeconds();
    OnAttackStart.Broadcast(Type);
    DoHitScan();
    GetWorldTimerManager().SetTimer(AttackTimer, this, &UMeleeCombatComponent::EndAttack, 0.3f, false);
}
void UMeleeCombatComponent::DoHitScan() {
    if (!GetOwner()) return;
    FVector Origin = GetOwner()->GetActorLocation();
    FVector Forward = GetOwner()->GetActorForwardVector();
    TArray<AActor*> Overlapping;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), Overlapping);
    for (AActor* A : Overlapping) {
        if (!IsValid(A) || A == GetOwner()) continue;
        FVector ToA = (A->GetActorLocation() - Origin);
        if (ToA.Size() <= AttackRange && FMath::Acos(FVector::DotProduct(Forward, ToA.GetSafeNormal())) <= FMath::DegreesToRadians(AttackAngle)) {
            OnMeleeHit.Broadcast(A, LightDamage);
            UGameplayStatics::ApplyDamage(A, LightDamage, GetOwner()->GetInstigatorController(), GetOwner(), nullptr);
        }
    }
}
void UMeleeCombatComponent::EndAttack() { bIsAttacking = false; }
void UMeleeCombatComponent::EnableHitbox(bool bEnable) { bIsAttacking = bEnable; if (bEnable) DoHitScan(); }"""

UNREAL_GAME_TEMPLATES["dash_ability"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DashComponent.generated.h"
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDash, FVector, Direction);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDashReady);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UDashComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UDashComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dash") float DashForce     = 3000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dash") float DashDuration  = 0.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dash") float DashCooldown  = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dash") int32 MaxDashCharges= 2;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dash") bool bDashInvincible= true;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 CurrentCharges;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsDashing = false;
    UPROPERTY(BlueprintAssignable) FOnDash      OnDash;
    UPROPERTY(BlueprintAssignable) FOnDashReady OnDashReady;
    UFUNCTION(BlueprintCallable) void Dash(FVector Direction);
    UFUNCTION(BlueprintCallable) void DashInDirection();
    UFUNCTION(BlueprintPure) bool CanDash() const { return CurrentCharges > 0 && !bIsDashing; }
    UFUNCTION(BlueprintPure) float GetCooldownPercent() const;
protected:
    virtual void BeginPlay() override;
private:
    FTimerHandle DashTimer;
    FTimerHandle CooldownTimer;
    float CooldownRemaining = 0.f;
    void EndDash();
    void RegainCharge();
};"""

UNREAL_GAME_TEMPLATES_CPP["dash_ability"] = """#include "DashComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
UDashComponent::UDashComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UDashComponent::BeginPlay() { Super::BeginPlay(); CurrentCharges = MaxDashCharges; }
void UDashComponent::DashInDirection() {
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (!Char) return;
    FVector Dir = Char->GetActorForwardVector();
    float H = Char->GetCharacterMovement()->GetLastInputVector().X;
    float V = Char->GetCharacterMovement()->GetLastInputVector().Y;
    if (!FMath::IsNearlyZero(H) || !FMath::IsNearlyZero(V))
        Dir = (Char->GetActorForwardVector()*V + Char->GetActorRightVector()*H).GetSafeNormal();
    Dash(Dir);
}
void UDashComponent::Dash(FVector Direction) {
    if (!CanDash()) return;
    CurrentCharges--; bIsDashing = true;
    OnDash.Broadcast(Direction);
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (Char) { Char->GetCharacterMovement()->BrakingFrictionFactor = 0.f; Char->LaunchCharacter(Direction * DashForce, true, true); }
    GetWorldTimerManager().SetTimer(DashTimer, this, &UDashComponent::EndDash, DashDuration, false);
    CooldownRemaining = DashCooldown;
    GetWorldTimerManager().SetTimer(CooldownTimer, this, &UDashComponent::RegainCharge, DashCooldown, false);
}
void UDashComponent::EndDash() {
    bIsDashing = false;
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (Char) Char->GetCharacterMovement()->BrakingFrictionFactor = 2.f;
}
void UDashComponent::RegainCharge() { CurrentCharges = FMath::Min(CurrentCharges + 1, MaxDashCharges); OnDashReady.Broadcast(); }
float UDashComponent::GetCooldownPercent() const { return DashCooldown > 0.f ? FMath::Clamp(CooldownRemaining / DashCooldown, 0.f, 1.f) : 0.f; }"""

UNREAL_GAME_TEMPLATES["wall_run"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WallRunComponent.generated.h"
UENUM(BlueprintType) enum class EWallSide : uint8 { None, Left, Right };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWallRun, EWallSide, Side);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnWallJump);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UWallRunComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UWallRunComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="WallRun") float WallRunSpeed   = 700.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="WallRun") float WallRunGravity = 0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="WallRun") float MaxWallRunTime = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="WallRun") float WallJumpForce  = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="WallRun") float WallDetectDist = 75.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsWallRunning = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EWallSide CurrentWallSide = EWallSide::None;
    UPROPERTY(BlueprintAssignable) FOnWallRun  OnWallRunStart;
    UPROPERTY(BlueprintAssignable) FOnWallJump OnWallJump;
    UFUNCTION(BlueprintCallable) void TryWallRun();
    UFUNCTION(BlueprintCallable) void WallJump();
    UFUNCTION(BlueprintCallable) void StopWallRun();
    UFUNCTION(BlueprintPure) bool IsWallRunning() const { return bIsWallRunning; }
protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
private:
    float WallRunTime = 0.f;
    FVector WallNormal;
    bool DetectWall(EWallSide Side, FHitResult& OutHit);
};"""

UNREAL_GAME_TEMPLATES_CPP["wall_run"] = """#include "WallRunComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
UWallRunComponent::UWallRunComponent() { PrimaryComponentTick.bCanEverTick = true; }
void UWallRunComponent::BeginPlay() { Super::BeginPlay(); }
void UWallRunComponent::TickComponent(float DeltaTime, ELevelTick T, FActorComponentTickFunction* F) {
    Super::TickComponent(DeltaTime, T, F);
    if (bIsWallRunning) { WallRunTime += DeltaTime; if (WallRunTime >= MaxWallRunTime) StopWallRun(); }
}
bool UWallRunComponent::DetectWall(EWallSide Side, FHitResult& OutHit) {
    if (!GetOwner()) return false;
    FVector Dir = Side == EWallSide::Left ? -GetOwner()->GetActorRightVector() : GetOwner()->GetActorRightVector();
    FVector Start = GetOwner()->GetActorLocation();
    return GetWorld()->LineTraceSingleByChannel(OutHit, Start, Start + Dir * WallDetectDist, ECC_Visibility);
}
void UWallRunComponent::TryWallRun() {
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (!Char || Char->GetCharacterMovement()->IsMovingOnGround()) return;
    FHitResult Hit;
    EWallSide Side = EWallSide::None;
    if (DetectWall(EWallSide::Left, Hit)) Side = EWallSide::Left;
    else if (DetectWall(EWallSide::Right, Hit)) Side = EWallSide::Right;
    if (Side == EWallSide::None) return;
    bIsWallRunning = true; WallRunTime = 0.f; CurrentWallSide = Side; WallNormal = Hit.Normal;
    Char->GetCharacterMovement()->GravityScale = WallRunGravity;
    Char->GetCharacterMovement()->Velocity = Char->GetActorForwardVector() * WallRunSpeed;
    OnWallRunStart.Broadcast(Side);
}
void UWallRunComponent::WallJump() {
    if (!bIsWallRunning) return;
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (!Char) return;
    StopWallRun();
    FVector JumpDir = (WallNormal + FVector(0.f, 0.f, 1.f)).GetSafeNormal();
    Char->LaunchCharacter(JumpDir * WallJumpForce, true, true);
    OnWallJump.Broadcast();
}
void UWallRunComponent::StopWallRun() {
    bIsWallRunning = false; CurrentWallSide = EWallSide::None; WallRunTime = 0.f;
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (Char) Char->GetCharacterMovement()->GravityScale = 1.f;
}"""

UNREAL_GAME_TEMPLATES["cover_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CoverComponent.generated.h"
UENUM(BlueprintType) enum class ECoverType : uint8 { None, Low, High, Corner };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnCoverChanged, bool, bInCover, ECoverType, Type);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UCoverComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UCoverComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cover") float CoverSearchRadius = 200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cover") float CoverEntrySpeed   = 400.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cover") float PeekOffset        = 80.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsInCover   = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bIsPeeking   = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) ECoverType CoverType = ECoverType::None;
    UPROPERTY(BlueprintAssignable) FOnCoverChanged OnCoverChanged;
    UFUNCTION(BlueprintCallable) bool TakeCover();
    UFUNCTION(BlueprintCallable) void LeaveCover();
    UFUNCTION(BlueprintCallable) void PeekLeft();
    UFUNCTION(BlueprintCallable) void PeekRight();
    UFUNCTION(BlueprintCallable) void StopPeeking();
    UFUNCTION(BlueprintPure) bool IsInCover() const { return bIsInCover; }
protected:
    virtual void BeginPlay() override;
private:
    FVector CoverNormal;
    FVector CoverLocation;
    bool FindCoverSpot(FVector& OutLocation, FVector& OutNormal, ECoverType& OutType);
};"""

UNREAL_GAME_TEMPLATES_CPP["cover_system"] = """#include "CoverComponent.h"
#include "GameFramework/Character.h"
UCoverComponent::UCoverComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UCoverComponent::BeginPlay() { Super::BeginPlay(); }
bool UCoverComponent::FindCoverSpot(FVector& OutLoc, FVector& OutNormal, ECoverType& OutType) {
    if (!GetOwner()) return false;
    FHitResult Hit;
    FVector Forward = GetOwner()->GetActorForwardVector();
    FVector Start = GetOwner()->GetActorLocation();
    if (GetWorld()->LineTraceSingleByChannel(Hit, Start, Start + Forward * CoverSearchRadius, ECC_Visibility)) {
        OutLoc = Hit.Location - Forward * 50.f; OutNormal = Hit.Normal;
        float WallHeight = Hit.GetActor() ? Hit.GetActor()->GetActorScale().Z * 100.f : 100.f;
        OutType = WallHeight > 150.f ? ECoverType::High : ECoverType::Low;
        return true;
    }
    return false;
}
bool UCoverComponent::TakeCover() {
    if (bIsInCover) return false;
    FVector Loc; FVector Normal; ECoverType Type;
    if (!FindCoverSpot(Loc, Normal, Type)) return false;
    bIsInCover = true; CoverLocation = Loc; CoverNormal = Normal; CoverType = Type;
    if (GetOwner()) GetOwner()->SetActorLocation(Loc);
    OnCoverChanged.Broadcast(true, CoverType);
    return true;
}
void UCoverComponent::LeaveCover() {
    if (!bIsInCover) return;
    bIsInCover = false; bIsPeeking = false; CoverType = ECoverType::None;
    OnCoverChanged.Broadcast(false, ECoverType::None);
}
void UCoverComponent::PeekLeft()  { if (bIsInCover && GetOwner()) { bIsPeeking = true; GetOwner()->SetActorLocation(CoverLocation + FVector(-PeekOffset, 0.f, 0.f)); } }
void UCoverComponent::PeekRight() { if (bIsInCover && GetOwner()) { bIsPeeking = true; GetOwner()->SetActorLocation(CoverLocation + FVector(PeekOffset,  0.f, 0.f)); } }
void UCoverComponent::StopPeeking() { if (bIsPeeking && GetOwner()) { bIsPeeking = false; GetOwner()->SetActorLocation(CoverLocation); } }"""

UNREAL_GAME_TEMPLATES["weapon_system"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WeaponSystemComponent.generated.h"
UENUM(BlueprintType) enum class EWeaponState : uint8 { Idle, Firing, Reloading, Empty, Switching };
UENUM(BlueprintType) enum class EFireMode  : uint8 { Single, Burst, Auto };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWeaponFired, FVector, HitLocation);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnWeaponReloaded);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnWeaponEmpty);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UWeaponSystemComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UWeaponSystemComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weapon") FString WeaponName   = "Rifle";
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weapon") EFireMode FireMode   = EFireMode::Single;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float  Damage         = 30.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float  Range          = 5000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float  FireRate        = 0.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") int32  MagazineSize   = 30;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") int32  ReserveAmmo    = 120;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float  ReloadTime     = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats") float  Spread         = 0.02f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32  CurrentAmmo;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EWeaponState WeaponState = EWeaponState::Idle;
    UPROPERTY(BlueprintAssignable) FOnWeaponFired   OnWeaponFired;
    UPROPERTY(BlueprintAssignable) FOnWeaponReloaded OnWeaponReloaded;
    UPROPERTY(BlueprintAssignable) FOnWeaponEmpty   OnWeaponEmpty;
    UFUNCTION(BlueprintCallable) void StartFire();
    UFUNCTION(BlueprintCallable) void StopFire();
    UFUNCTION(BlueprintCallable) void Reload();
    UFUNCTION(BlueprintPure) bool CanFire() const;
    UFUNCTION(BlueprintPure) float GetAmmoPercent() const;
protected:
    virtual void BeginPlay() override;
private:
    float LastFireTime = -999.f;
    FTimerHandle FireTimer;
    FTimerHandle ReloadTimer;
    void FireOnce();
    void FinishReload();
    void DoLineTrace();
};"""

UNREAL_GAME_TEMPLATES_CPP["weapon_system"] = """#include "WeaponSystemComponent.h"
#include "Kismet/GameplayStatics.h"
#include "DrawDebugHelpers.h"
UWeaponSystemComponent::UWeaponSystemComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UWeaponSystemComponent::BeginPlay() { Super::BeginPlay(); CurrentAmmo = MagazineSize; }
bool UWeaponSystemComponent::CanFire() const { return WeaponState == EWeaponState::Idle && CurrentAmmo > 0 && GetWorld()->GetTimeSeconds() - LastFireTime >= FireRate; }
float UWeaponSystemComponent::GetAmmoPercent() const { return MagazineSize > 0 ? (float)CurrentAmmo / MagazineSize : 0.f; }
void UWeaponSystemComponent::StartFire() {
    if (!CanFire()) { if (CurrentAmmo <= 0) { OnWeaponEmpty.Broadcast(); Reload(); } return; }
    FireOnce();
    if (FireMode == EFireMode::Auto) GetWorldTimerManager().SetTimer(FireTimer, this, &UWeaponSystemComponent::FireOnce, FireRate, true);
}
void UWeaponSystemComponent::StopFire() { GetWorldTimerManager().ClearTimer(FireTimer); }
void UWeaponSystemComponent::FireOnce() {
    if (!CanFire()) { StopFire(); return; }
    CurrentAmmo--; LastFireTime = GetWorld()->GetTimeSeconds();
    DoLineTrace();
}
void UWeaponSystemComponent::DoLineTrace() {
    if (!GetOwner()) return;
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC) return;
    FVector Start, Dir; PC->DeprojectMousePositionToWorld(Start, Dir);
    FVector SpreadDir = Dir + FVector(FMath::FRandRange(-Spread,Spread), FMath::FRandRange(-Spread,Spread), 0.f);
    FVector End = Start + SpreadDir.GetSafeNormal() * Range;
    FHitResult Hit;
    FCollisionQueryParams Params; Params.AddIgnoredActor(GetOwner());
    if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params)) {
        UGameplayStatics::ApplyDamage(Hit.GetActor(), Damage, PC, GetOwner(), nullptr);
        OnWeaponFired.Broadcast(Hit.Location);
    } else { OnWeaponFired.Broadcast(End); }
}
void UWeaponSystemComponent::Reload() {
    if (WeaponState == EWeaponState::Reloading || ReserveAmmo <= 0) return;
    WeaponState = EWeaponState::Reloading; StopFire();
    GetWorldTimerManager().SetTimer(ReloadTimer, this, &UWeaponSystemComponent::FinishReload, ReloadTime, false);
}
void UWeaponSystemComponent::FinishReload() {
    int32 Needed = MagazineSize - CurrentAmmo; int32 Got = FMath::Min(Needed, ReserveAmmo);
    CurrentAmmo += Got; ReserveAmmo -= Got; WeaponState = EWeaponState::Idle;
    OnWeaponReloaded.Broadcast();
}"""

UNREAL_GAME_TEMPLATES["inventory_advanced"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AdvancedInventoryComponent.generated.h"
UENUM(BlueprintType) enum class EItemType : uint8 { Weapon, Armor, Consumable, Quest, Key, Currency, Ammo, Material };
USTRUCT(BlueprintType) struct FInventoryItem {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString    ID;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString    Name;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString    Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EItemType  Type = EItemType::Consumable;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32      Quantity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32      MaxStack = 99;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float      Weight = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32      Value = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool       bIsEquipped = false;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnItemAdded,   FInventoryItem, Item);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnItemRemoved, FString, ItemID);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnItemUsed,  FString, ItemID, AActor*, User);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAdvancedInventoryComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UAdvancedInventoryComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Inventory") int32   MaxSlots      = 40;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Inventory") float   MaxWeight     = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Inventory") TArray<FInventoryItem> Items;
    UPROPERTY(BlueprintAssignable) FOnItemAdded   OnItemAdded;
    UPROPERTY(BlueprintAssignable) FOnItemRemoved OnItemRemoved;
    UPROPERTY(BlueprintAssignable) FOnItemUsed    OnItemUsed;
    UFUNCTION(BlueprintCallable) bool AddItem(FInventoryItem Item);
    UFUNCTION(BlueprintCallable) bool RemoveItem(FString ItemID, int32 Amount = 1);
    UFUNCTION(BlueprintCallable) bool UseItem(FString ItemID);
    UFUNCTION(BlueprintCallable) bool EquipItem(FString ItemID);
    UFUNCTION(BlueprintCallable) void DropItem(FString ItemID, int32 Amount = 1);
    UFUNCTION(BlueprintCallable) void SortInventory(EItemType SortByType);
    UFUNCTION(BlueprintPure) bool HasItem(FString ItemID, int32 Amount = 1) const;
    UFUNCTION(BlueprintPure) int32 GetItemCount(FString ItemID) const;
    UFUNCTION(BlueprintPure) float GetCurrentWeight() const;
    UFUNCTION(BlueprintPure) bool IsFull() const { return Items.Num() >= MaxSlots; }
protected:
    virtual void BeginPlay() override;
};"""

UNREAL_GAME_TEMPLATES_CPP["inventory_advanced"] = """#include "AdvancedInventoryComponent.h"
UAdvancedInventoryComponent::UAdvancedInventoryComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UAdvancedInventoryComponent::BeginPlay() { Super::BeginPlay(); }
bool UAdvancedInventoryComponent::AddItem(FInventoryItem Item) {
    if (GetCurrentWeight() + Item.Weight * Item.Quantity > MaxWeight) return false;
    for (FInventoryItem& Existing : Items) {
        if (Existing.ID == Item.ID && Existing.Quantity < Existing.MaxStack) {
            int32 CanAdd = FMath::Min(Item.Quantity, Existing.MaxStack - Existing.Quantity);
            Existing.Quantity += CanAdd; Item.Quantity -= CanAdd;
            if (Item.Quantity <= 0) { OnItemAdded.Broadcast(Item); return true; }
        }
    }
    if (IsFull()) return false;
    Items.Add(Item); OnItemAdded.Broadcast(Item); return true;
}
bool UAdvancedInventoryComponent::RemoveItem(FString ItemID, int32 Amount) {
    for (int32 i = Items.Num()-1; i >= 0; i--) {
        if (Items[i].ID == ItemID) {
            Items[i].Quantity -= Amount;
            if (Items[i].Quantity <= 0) Items.RemoveAt(i);
            OnItemRemoved.Broadcast(ItemID); return true;
        }
    }
    return false;
}
bool UAdvancedInventoryComponent::UseItem(FString ItemID) {
    for (auto& I : Items) if (I.ID == ItemID) { OnItemUsed.Broadcast(ItemID, GetOwner()); if (I.Type == EItemType::Consumable) RemoveItem(ItemID, 1); return true; }
    return false;
}
bool UAdvancedInventoryComponent::EquipItem(FString ItemID) { for (auto& I : Items) if (I.ID == ItemID) { I.bIsEquipped = !I.bIsEquipped; return true; } return false; }
void UAdvancedInventoryComponent::DropItem(FString ItemID, int32 Amount) { RemoveItem(ItemID, Amount); }
void UAdvancedInventoryComponent::SortInventory(EItemType SortByType) { Items.Sort([SortByType](const FInventoryItem& A, const FInventoryItem& B){ return A.Type == SortByType && B.Type != SortByType; }); }
bool UAdvancedInventoryComponent::HasItem(FString ItemID, int32 Amount) const { for (auto& I : Items) if (I.ID == ItemID && I.Quantity >= Amount) return true; return false; }
int32 UAdvancedInventoryComponent::GetItemCount(FString ItemID) const { for (auto& I : Items) if (I.ID == ItemID) return I.Quantity; return 0; }
float UAdvancedInventoryComponent::GetCurrentWeight() const { float W = 0.f; for (auto& I : Items) W += I.Weight * I.Quantity; return W; }"""

UNREAL_GAME_TEMPLATES["dialogue_advanced"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DialogueSystemComponent.generated.h"
UENUM(BlueprintType) enum class EDialogueNodeType : uint8 { Normal, Choice, Condition, End };
USTRUCT(BlueprintType) struct FDialogueChoice {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FText   ChoiceText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   NextNodeIndex = -1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString RequiredFlag;
};
USTRUCT(BlueprintType) struct FDialogueNode {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString   Speaker;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(MultiLine)) FText Text;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EDialogueNodeType NodeType = EDialogueNodeType::Normal;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FDialogueChoice> Choices;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 NextNodeIndex = -1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString SetFlag;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnDialogueNode, FDialogueNode, Node, int32, Index);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDialogueFinished);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UDialogueSystemComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UDialogueSystemComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dialogue") TArray<FDialogueNode> Nodes;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Dialogue") TSet<FString> ActiveFlags;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32  CurrentNodeIndex = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool   bIsActive = false;
    UPROPERTY(BlueprintAssignable) FOnDialogueNode     OnDialogueNode;
    UPROPERTY(BlueprintAssignable) FOnDialogueFinished OnDialogueFinished;
    UFUNCTION(BlueprintCallable) void StartDialogue(int32 StartNode = 0);
    UFUNCTION(BlueprintCallable) void AdvanceDialogue();
    UFUNCTION(BlueprintCallable) void SelectChoice(int32 ChoiceIndex);
    UFUNCTION(BlueprintCallable) void EndDialogue();
    UFUNCTION(BlueprintPure) FDialogueNode GetCurrentNode() const;
    UFUNCTION(BlueprintPure) bool HasChoices() const;
protected:
    virtual void BeginPlay() override;
private:
    void ProcessNode(int32 NodeIndex);
};"""

UNREAL_GAME_TEMPLATES_CPP["dialogue_advanced"] = """#include "DialogueSystemComponent.h"
UDialogueSystemComponent::UDialogueSystemComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UDialogueSystemComponent::BeginPlay() { Super::BeginPlay(); }
void UDialogueSystemComponent::StartDialogue(int32 StartNode) { bIsActive = true; ProcessNode(StartNode); }
void UDialogueSystemComponent::ProcessNode(int32 NodeIndex) {
    if (!Nodes.IsValidIndex(NodeIndex)) { EndDialogue(); return; }
    CurrentNodeIndex = NodeIndex;
    FDialogueNode& Node = Nodes[NodeIndex];
    if (!Node.SetFlag.IsEmpty()) ActiveFlags.Add(Node.SetFlag);
    OnDialogueNode.Broadcast(Node, NodeIndex);
    if (Node.NodeType == EDialogueNodeType::End) EndDialogue();
}
void UDialogueSystemComponent::AdvanceDialogue() {
    if (!bIsActive || !Nodes.IsValidIndex(CurrentNodeIndex)) return;
    FDialogueNode& Node = Nodes[CurrentNodeIndex];
    if (Node.NodeType == EDialogueNodeType::Choice) return;
    int32 Next = Node.NextNodeIndex;
    if (Next < 0) { EndDialogue(); return; }
    ProcessNode(Next);
}
void UDialogueSystemComponent::SelectChoice(int32 ChoiceIndex) {
    if (!bIsActive || !Nodes.IsValidIndex(CurrentNodeIndex)) return;
    auto& Choices = Nodes[CurrentNodeIndex].Choices;
    if (!Choices.IsValidIndex(ChoiceIndex)) return;
    auto& Choice = Choices[ChoiceIndex];
    if (!Choice.RequiredFlag.IsEmpty() && !ActiveFlags.Contains(Choice.RequiredFlag)) return;
    if (Choice.NextNodeIndex < 0) { EndDialogue(); return; }
    ProcessNode(Choice.NextNodeIndex);
}
void UDialogueSystemComponent::EndDialogue() { bIsActive = false; OnDialogueFinished.Broadcast(); }
FDialogueNode UDialogueSystemComponent::GetCurrentNode() const { return Nodes.IsValidIndex(CurrentNodeIndex) ? Nodes[CurrentNodeIndex] : FDialogueNode(); }
bool UDialogueSystemComponent::HasChoices() const { return Nodes.IsValidIndex(CurrentNodeIndex) && Nodes[CurrentNodeIndex].NodeType == EDialogueNodeType::Choice; }"""

UNREAL_GAME_TEMPLATES["quest_advanced"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "QuestSystemComponent.generated.h"
UENUM(BlueprintType) enum class EQuestStatus : uint8 { Locked, Available, Active, Completed, Failed };
UENUM(BlueprintType) enum class EObjectiveType : uint8 { Kill, Collect, Reach, Talk, Interact, Survive, Protect };
USTRUCT(BlueprintType) struct FQuestObjective {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EObjectiveType Type = EObjectiveType::Kill;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString TargetTag;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32   Required = 1;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 Current = 0;
    bool IsComplete() const { return Current >= Required; }
};
USTRUCT(BlueprintType) struct FQuest {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ID;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString Title;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(MultiLine)) FText Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FQuestObjective> Objectives;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32  RewardScore = 500;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FString> RewardItems;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EQuestStatus Status = EQuestStatus::Available;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FString> PrerequisiteIDs;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestStarted,   FQuest, Quest);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestCompleted, FQuest, Quest);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestFailed,    FQuest, Quest);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnObjectiveUpdated, FString, QuestID, int32, ObjectiveIndex);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UQuestSystemComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UQuestSystemComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Quests") TArray<FQuest> AllQuests;
    UPROPERTY(BlueprintAssignable) FOnQuestStarted     OnQuestStarted;
    UPROPERTY(BlueprintAssignable) FOnQuestCompleted   OnQuestCompleted;
    UPROPERTY(BlueprintAssignable) FOnQuestFailed      OnQuestFailed;
    UPROPERTY(BlueprintAssignable) FOnObjectiveUpdated OnObjectiveUpdated;
    UFUNCTION(BlueprintCallable) bool StartQuest(FString QuestID);
    UFUNCTION(BlueprintCallable) void UpdateObjective(FString QuestID, EObjectiveType Type, FString Tag, int32 Amount = 1);
    UFUNCTION(BlueprintCallable) void FailQuest(FString QuestID);
    UFUNCTION(BlueprintCallable) void AbandonQuest(FString QuestID);
    UFUNCTION(BlueprintPure) TArray<FQuest> GetActiveQuests() const;
    UFUNCTION(BlueprintPure) bool IsQuestComplete(FString QuestID) const;
    UFUNCTION(BlueprintPure) bool HasPrerequisites(FString QuestID) const;
protected:
    virtual void BeginPlay() override;
private:
    FQuest* FindQuest(FString QuestID);
    void CheckQuestCompletion(FQuest& Quest);
};"""

UNREAL_GAME_TEMPLATES_CPP["quest_advanced"] = """#include "QuestSystemComponent.h"
UQuestSystemComponent::UQuestSystemComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UQuestSystemComponent::BeginPlay() { Super::BeginPlay(); }
FQuest* UQuestSystemComponent::FindQuest(FString QuestID) { for (auto& Q : AllQuests) if (Q.ID == QuestID) return &Q; return nullptr; }
bool UQuestSystemComponent::StartQuest(FString QuestID) {
    FQuest* Q = FindQuest(QuestID);
    if (!Q || Q->Status != EQuestStatus::Available || !HasPrerequisites(QuestID)) return false;
    Q->Status = EQuestStatus::Active; OnQuestStarted.Broadcast(*Q); return true;
}
void UQuestSystemComponent::UpdateObjective(FString QuestID, EObjectiveType Type, FString Tag, int32 Amount) {
    FQuest* Q = FindQuest(QuestID);
    if (!Q || Q->Status != EQuestStatus::Active) return;
    for (int32 i = 0; i < Q->Objectives.Num(); i++) {
        auto& Obj = Q->Objectives[i];
        if (Obj.Type == Type && Obj.TargetTag == Tag && !Obj.IsComplete()) {
            Obj.Current = FMath::Min(Obj.Current + Amount, Obj.Required);
            OnObjectiveUpdated.Broadcast(QuestID, i);
        }
    }
    CheckQuestCompletion(*Q);
}
void UQuestSystemComponent::CheckQuestCompletion(FQuest& Quest) {
    bool bAllDone = true; for (auto& O : Quest.Objectives) if (!O.IsComplete()) { bAllDone = false; break; }
    if (bAllDone) { Quest.Status = EQuestStatus::Completed; OnQuestCompleted.Broadcast(Quest); }
}
void UQuestSystemComponent::FailQuest(FString QuestID)    { FQuest* Q = FindQuest(QuestID); if (Q && Q->Status == EQuestStatus::Active) { Q->Status = EQuestStatus::Failed;    OnQuestFailed.Broadcast(*Q); } }
void UQuestSystemComponent::AbandonQuest(FString QuestID) { FQuest* Q = FindQuest(QuestID); if (Q && Q->Status == EQuestStatus::Active) { Q->Status = EQuestStatus::Available; } }
TArray<FQuest> UQuestSystemComponent::GetActiveQuests() const { TArray<FQuest> R; for (auto& Q : AllQuests) if (Q.Status == EQuestStatus::Active) R.Add(Q); return R; }
bool UQuestSystemComponent::IsQuestComplete(FString QuestID) const { for (auto& Q : AllQuests) if (Q.ID == QuestID) return Q.Status == EQuestStatus::Completed; return false; }
bool UQuestSystemComponent::HasPrerequisites(FString QuestID) const { FQuest* Q = const_cast<UQuestSystemComponent*>(this)->FindQuest(QuestID); if (!Q) return false; for (auto& P : Q->PrerequisiteIDs) if (!IsQuestComplete(P)) return false; return true; }"""

UNREAL_GAME_TEMPLATES["movement_advanced"] = """#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AdvancedMovementComponent.generated.h"
UENUM(BlueprintType) enum class EMovementState : uint8 { Walking, Running, Crouching, Sliding, Climbing, Swimming, Flying };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnMovementStateChanged, EMovementState, OldState, EMovementState, NewState);
UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UAdvancedMovementComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UAdvancedMovementComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float WalkSpeed   = 400.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float RunSpeed    = 700.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float CrouchSpeed = 200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float SlideSpeed  = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float ClimbSpeed  = 200.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Speed") float SwimSpeed   = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Jump")  float JumpHeight  = 420.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Jump")  int32 MaxJumps    = 2;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Slide") float SlideDuration = 0.8f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Slide") float SlideCooldown = 1.5f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) EMovementState State = EMovementState::Walking;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 JumpsLeft = 2;
    UPROPERTY(BlueprintAssignable) FOnMovementStateChanged OnStateChanged;
    UFUNCTION(BlueprintCallable) void SetState(EMovementState NewState);
    UFUNCTION(BlueprintCallable) void StartRun()    { SetState(EMovementState::Running); }
    UFUNCTION(BlueprintCallable) void StopRun()     { SetState(EMovementState::Walking); }
    UFUNCTION(BlueprintCallable) void StartCrouch() { SetState(EMovementState::Crouching); }
    UFUNCTION(BlueprintCallable) void StopCrouch()  { SetState(EMovementState::Walking); }
    UFUNCTION(BlueprintCallable) void TrySlide();
    UFUNCTION(BlueprintCallable) void Jump();
    UFUNCTION(BlueprintCallable) void OnLanded();
    UFUNCTION(BlueprintPure) bool CanSlide() const;
    UFUNCTION(BlueprintPure) bool CanJump() const { return JumpsLeft > 0; }
protected:
    virtual void BeginPlay() override;
private:
    float LastSlideTime = -999.f;
    FTimerHandle SlideTimer;
    void ApplySpeedForState(EMovementState InState);
    void EndSlide();
};"""

UNREAL_GAME_TEMPLATES_CPP["movement_advanced"] = """#include "AdvancedMovementComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
UAdvancedMovementComponent::UAdvancedMovementComponent() { PrimaryComponentTick.bCanEverTick = false; }
void UAdvancedMovementComponent::BeginPlay() { Super::BeginPlay(); JumpsLeft = MaxJumps; ApplySpeedForState(State); }
void UAdvancedMovementComponent::SetState(EMovementState New) {
    EMovementState Old = State; State = New;
    ApplySpeedForState(New); OnStateChanged.Broadcast(Old, New);
}
void UAdvancedMovementComponent::ApplySpeedForState(EMovementState S) {
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (!Char) return;
    float Speed = WalkSpeed;
    switch (S) {
        case EMovementState::Running:   Speed = RunSpeed;    break;
        case EMovementState::Crouching: Speed = CrouchSpeed; Char->Crouch(); break;
        case EMovementState::Sliding:   Speed = SlideSpeed;  break;
        case EMovementState::Swimming:  Speed = SwimSpeed;   break;
        case EMovementState::Climbing:  Speed = ClimbSpeed;  break;
        default: if (Char->bIsCrouched) Char->UnCrouch(); break;
    }
    Char->GetCharacterMovement()->MaxWalkSpeed = Speed;
}
bool UAdvancedMovementComponent::CanSlide() const { return State == EMovementState::Running && GetWorld()->GetTimeSeconds() - LastSlideTime >= SlideCooldown; }
void UAdvancedMovementComponent::TrySlide() {
    if (!CanSlide()) return; LastSlideTime = GetWorld()->GetTimeSeconds(); SetState(EMovementState::Sliding);
    GetWorldTimerManager().SetTimer(SlideTimer, this, &UAdvancedMovementComponent::EndSlide, SlideDuration, false);
}
void UAdvancedMovementComponent::EndSlide() { SetState(EMovementState::Walking); }
void UAdvancedMovementComponent::Jump() {
    if (!CanJump()) return; JumpsLeft--;
    ACharacter* Char = Cast<ACharacter>(GetOwner());
    if (Char) Char->LaunchCharacter(FVector(0.f, 0.f, JumpHeight), false, true);
}
void UAdvancedMovementComponent::OnLanded() { JumpsLeft = MaxJumps; if (State == EMovementState::Sliding) EndSlide(); }"""


UNREAL_GAME_KEYWORDS.update({
    "melee_combat": ['melee', 'sword', 'punch', 'kick', 'close combat', 'hand to hand', 'brawl'],
    "dash_ability": ['dash', 'blink', 'dodge roll', 'quick dash', 'dodge'],
    "wall_run": ['wall run', 'parkour', 'wall jump', 'run on wall'],
    "cover_system": ['cover', 'take cover', 'peek', 'behind cover', 'crouch cover'],
    "weapon_system": ['weapon system', 'gun system', 'fire weapon', 'shooting system', 'shooter weapon'],
    "inventory_advanced": ['inventory system', 'advanced inventory', 'item management', 'bag system'],
    "dialogue_advanced": ['dialogue system', 'dialogue tree', 'branching dialogue', 'npc dialogue', 'choice dialogue'],
    "quest_advanced": ['quest system', 'mission system', 'objective system', 'quest tracker'],
    "movement_advanced": ['advanced movement', 'movement system', 'parkour movement', 'sprint slide'],
})

def save_unreal_scripts(matches: list, folder_name: str) -> bool:
    """
    Validate and save Unreal .h + .cpp files.
    Called from extract_and_save_scripts when domain == 'unreal'.
    """
    import os, re

    if len(matches) < 2:
        if len(matches) == 1:
            # LLM returned only 1 block — try to split header vs cpp
            code = matches[0]
            if "#pragma once" in code and "::" in code:
                # Contains both header and impl — split at first ::
                lines = code.split("\n")
                split = next((i for i,l in enumerate(lines) if "::" in l and not l.strip().startswith("//")), -1)
                if split > 0:
                    matches = ["\n".join(lines[:split]), "\n".join(lines[split:])]
                    print("⚠ Auto-split single block into header+cpp", flush=True)
            if len(matches) < 2:
                print("❌ Unreal requires header and cpp blocks.")
                return False
        else:
            print("❌ Unreal requires header and cpp blocks.")
            return False

    header_code = matches[0].strip()
    cpp_code    = matches[1].strip()

    # Fix .generated.h name mismatch first
    header_code = fix_generated_h_name(header_code)

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

    # Extract class name
    m = re.search(r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", header_code)
    class_name = m.group(1) if m else "UnrealClass"

    # Apply comprehensive auto-fixes before saving
    header_code, cpp_code = auto_fix_unreal_code(header_code, cpp_code, class_name)

    # Re-extract class name in case self-inheritance fix renamed it
    m2 = re.search(r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", header_code)
    if m2:
        class_name = m2.group(1)

    header_path = os.path.join(folder_name, f"{class_name}.h")
    cpp_path    = os.path.join(folder_name, f"{class_name}.cpp")

    with open(header_path, "w", encoding="utf-8") as f: f.write(header_code)
    with open(cpp_path,    "w", encoding="utf-8") as f: f.write(cpp_code)

    print(f"\n💾 Saved -> {header_path}")
    print(f"💾 Saved -> {cpp_path}")
    return True
