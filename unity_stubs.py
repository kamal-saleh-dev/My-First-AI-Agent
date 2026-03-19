# unity_stubs.py
UNITY_STUBS = r"""
// Unity Engine Stubs — for compile validation only
using System;
using System.Collections;
using System.Collections.Generic;

namespace UnityEngine {
    // ===== Unity Attributes =====
    public class HeaderAttribute : Attribute { public HeaderAttribute(string h){} }
    public class TooltipAttribute : Attribute { public TooltipAttribute(string t){} }
    public class SerializeField : Attribute {}
    public class RangeAttribute : Attribute { public RangeAttribute(float min, float max){} }
    public class HideInInspector : Attribute {}
    public class RequireComponent : Attribute { public RequireComponent(Type t){} }
    public class DisallowMultipleComponent : Attribute {}
    public class ExecuteInEditMode : Attribute {}
    // ===== Core Classes =====
    public class Object { public string name; public static void Destroy(Object o, float t=0f){} public static T FindObjectOfType<T>() where T:Object => null; }
    public class Component : Object { public GameObject gameObject; public Transform transform; public T GetComponent<T>() where T:Component => null; public T[] GetComponents<T>() where T:Component => null; }
    public class Behaviour : Component { public bool enabled; }
    public class MonoBehaviour : Behaviour {
        public void StartCoroutine(IEnumerator r){}
        public void StopCoroutine(IEnumerator r){}
        public void Invoke(string m, float t){}
        public void InvokeRepeating(string m, float t, float r){}
        public void CancelInvoke(string m){}
        public static T Instantiate<T>(T o) where T:Object => o;
        public static T Instantiate<T>(T o, Vector3 p, Quaternion r) where T:Object => o;
        public static GameObject[] FindGameObjectsWithTag(string t) => new GameObject[0];
        public static void DontDestroyOnLoad(Object o){}
    }
    public class GameObject : Object {
        public Transform transform = new Transform();
        public bool activeSelf;
        public string tag;
        public T GetComponent<T>() where T:Component => null;
        public T AddComponent<T>() where T:Component => null;
        public void SetActive(bool v){}
        public static GameObject Find(string n) => null;
        public static GameObject[] FindGameObjectsWithTag(string t) => new GameObject[0];
        public static T FindObjectOfType<T>() where T:MonoBehaviour => null;
        public static T[] FindObjectsOfType<T>() where T:MonoBehaviour => null;
    }
    public class Transform : Component {
        public Vector3 position; public Vector3 localPosition; public Vector3 localScale;
        public Vector3 eulerAngles; public Quaternion rotation; public Quaternion localRotation;
        public Transform parent; public Vector3 up; public Vector3 right; public Vector3 forward;
        public int childCount;
        public void Translate(Vector3 v){}
        public void Rotate(float x, float y, float z){}
        public void LookAt(Transform t){}
        public Transform GetChild(int i) => null;
    }
    public struct Vector2 {
        public float x, y;
        public Vector2(float x, float y){this.x=x;this.y=y;}
        public static Vector2 zero = new Vector2(0,0);
        public static Vector2 up = new Vector2(0,1);
        public static Vector2 down = new Vector2(0,-1);
        public static Vector2 left = new Vector2(-1,0);
        public static Vector2 right = new Vector2(1,0);
        public static Vector2 operator+(Vector2 a, Vector2 b) => new Vector2(a.x+b.x,a.y+b.y);
        public static Vector2 operator*(Vector2 a, float b) => new Vector2(a.x*b,a.y*b);
        public static Vector2 operator*(float b, Vector2 a) => new Vector2(a.x*b,a.y*b);
        public static float Distance(Vector2 a, Vector2 b) => 0f;
        public static Vector2 ClampMagnitude(Vector2 v, float m) => v;
        public Vector2 normalized => this;
        public float magnitude => 0f;
    }
    public struct Vector2Int {
        public int x, y;
        public Vector2Int(int x, int y){this.x=x;this.y=y;}
        public static Vector2Int zero = new Vector2Int(0,0);
        public static Vector2Int operator+(Vector2Int a, Vector2Int b) => new Vector2Int(a.x+b.x, a.y+b.y);
        public static Vector2Int operator-(Vector2Int a, Vector2Int b) => new Vector2Int(a.x-b.x, a.y-b.y);
        public static Vector2Int operator*(Vector2Int a, int b) => new Vector2Int(a.x*b, a.y*b);
        public static bool operator==(Vector2Int a, Vector2Int b) => a.x==b.x && a.y==b.y;
        public static bool operator!=(Vector2Int a, Vector2Int b) => !(a==b);
        public override bool Equals(object o) => false;
        public override int GetHashCode() => x*1000+y;
    }
    public struct Vector3 {
        public float x, y, z;
        public Vector3(float x, float y, float z=0){this.x=x;this.y=y;this.z=z;}
        public static Vector3 zero = new Vector3(0,0,0);
        public static Vector3 up = new Vector3(0,1,0);
        public static Vector3 down = new Vector3(0,-1,0);
        public static Vector3 forward = new Vector3(0,0,1);
        public static Vector3 right = new Vector3(1,0,0);
        public static Vector3 operator+(Vector3 a, Vector3 b) => new Vector3(a.x+b.x,a.y+b.y,a.z+b.z);
        public static Vector3 operator*(Vector3 a, float b) => new Vector3(a.x*b,a.y*b,a.z*b);
        public static Vector3 operator*(float b, Vector3 a) => new Vector3(a.x*b,a.y*b,a.z*b);
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) => a;
        public static float Distance(Vector3 a, Vector3 b) => 0f;
        public Vector3 normalized => this;
        public float magnitude => 0f;
    }
    public struct Quaternion {
        public float x,y,z,w;
        public static Quaternion identity = new Quaternion();
        public static Quaternion AngleAxis(float a, Vector3 ax) => new Quaternion();
        public static Quaternion Euler(float x, float y, float z) => new Quaternion();
        public static Quaternion Slerp(Quaternion a, Quaternion b, float t) => a;
        public static Quaternion LookRotation(Vector3 v) => new Quaternion();
    }
    public class Rigidbody2D : Component {
        public Vector2 velocity; public float rotation; public float gravityScale; public bool isKinematic;
        public void AddForce(Vector2 f){}
        public void AddForce(Vector2 f, ForceMode2D m){}
        public void AddTorque(float t){}
        public void MovePosition(Vector2 p){}
    }
    public enum ForceMode2D { Force, Impulse }
    public class Collider2D : Component { public bool isTrigger; public string tag; public GameObject gameObject; public bool CompareTag(string t) => false; }
    public class Collider : Component { public bool isTrigger; public string tag; public GameObject gameObject; public bool CompareTag(string t) => false; }
    public class Collision2D { public GameObject gameObject; public Collider2D collider; public ContactPoint2D[] contacts; public Vector2 relativeVelocity; }
    public class Collision { public GameObject gameObject; public Collider collider; }
    public struct ContactPoint2D { public Vector2 point; public Vector2 normal; }
    public class SpriteRenderer : Component { public Sprite sprite; public Color color; }
    public class Sprite : Object {}
    public class Material : Object { public void SetTextureOffset(string n, Vector2 v){} }
    public class Renderer : Component { public Material material; public Material sharedMaterial; }
    public class Camera : Component {
        public float orthographicSize;
        public Transform transform = new Transform();
        public static Camera main = new Camera();
        public Vector3 ScreenToWorldPoint(Vector3 v) => Vector3.zero;
    }
    public class AudioSource : Component { public AudioClip clip; public float volume; public bool loop; public void Play(){} public void Stop(){} public void PlayOneShot(AudioClip c){} }
    public class AudioClip : Object {}
    public class Animator : Component { public void SetTrigger(string n){} public void SetBool(string n, bool v){} public void SetFloat(string n, float v){} public void SetInteger(string n, int v){} }
    public class ParticleSystem : Component { public void Play(){} public void Stop(){} }
    public struct Color { public float r,g,b,a; public static Color white=new Color(); public static Color red=new Color(); public static Color green=new Color(); public static Color blue=new Color(); public static Color black=new Color(); public static Color yellow=new Color(); public Color(float r,float g,float b,float a=1){this.r=r;this.g=g;this.b=b;this.a=a;} }
    public struct Rect { public float x,y,width,height; }
    public class LayerMask { public static int NameToLayer(string n) => 0; public static implicit operator int(LayerMask m) => 0; public static implicit operator LayerMask(int m) => new LayerMask(); }
    public static class Mathf {
        public static float PI = 3.14159f;
        public static float Clamp(float v, float mn, float mx) => v;
        public static int Clamp(int v, int mn, int mx) => v;
        public static float Clamp01(float v) => v;
        public static float Lerp(float a, float b, float t) => a;
        public static float MoveTowards(float c, float t, float d) => c;
        public static float Abs(float v) => v < 0 ? -v : v;
        public static int Abs(int v) => v < 0 ? -v : v;
        public static float Max(float a, float b) => a > b ? a : b;
        public static float Min(float a, float b) => a < b ? a : b;
        public static int Max(int a, int b) => a > b ? a : b;
        public static int Min(int a, int b) => a < b ? a : b;
        public static float Sqrt(float v) => (float)Math.Sqrt(v);
        public static float Pow(float b, float e) => (float)Math.Pow(b,e);
        public static float Sin(float v) => (float)Math.Sin(v);
        public static float Cos(float v) => (float)Math.Cos(v);
        public static float Atan2(float y, float x) => (float)Math.Atan2(y,x);
        public static float Deg2Rad = 0.0174533f;
        public static float Rad2Deg = 57.2958f;
        public static float Sign(float v) => v >= 0 ? 1f : -1f;
        public static float Round(float v) => (float)Math.Round(v);
        public static int RoundToInt(float v) => (int)Math.Round(v);
        public static float Floor(float v) => (float)Math.Floor(v);
        public static int FloorToInt(float v) => (int)Math.Floor(v);
        public static float Ceil(float v) => (float)Math.Ceiling(v);
        public static int CeilToInt(float v) => (int)Math.Ceiling(v);
        public static bool Approximately(float a, float b) => Math.Abs(a-b) < 1e-5f;
        public static float Infinity = float.PositiveInfinity;
        public static float NegativeInfinity = float.NegativeInfinity;
        public static float SmoothDamp(float c, float t, ref float v, float st) => c;
        public static Vector3 MoveTowards(Vector3 c, Vector3 t, float d) => c;
        public static float MoveTowardsAngle(float c, float t, float d) => c;
        public static float DeltaAngle(float c, float t) => 0f;
    }
    public static class Random {
        public static float value => 0.5f;
        public static int Range(int min, int max) => min;
        public static float Range(float min, float max) => min;
        public static Vector3 insideUnitCircle => Vector3.zero;
    }
    public static class Time {
        public static float deltaTime = 0.016f;
        public static float fixedDeltaTime = 0.02f;
        public static float time = 0f;
        public static float timeScale = 1f;
        public static float unscaledDeltaTime = 0.016f;
    }
    public static class Input {
        public static float GetAxis(string n) => 0f;
        public static float GetAxisRaw(string n) => 0f;
        public static bool GetKey(KeyCode k) => false;
        public static bool GetKeyDown(KeyCode k) => false;
        public static bool GetKeyUp(KeyCode k) => false;
        public static bool GetButton(string n) => false;
        public static bool GetButtonDown(string n) => false;
        public static bool GetButtonUp(string n) => false;
        public static bool GetMouseButton(int b) => false;
        public static bool GetMouseButtonDown(int b) => false;
        public static Vector3 mousePosition => Vector3.zero;
        public static bool anyKey => false;
        public static bool anyKeyDown => false;
    }
    public enum KeyCode { None, Space, Return, Escape, A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z,
        UpArrow, DownArrow, LeftArrow, RightArrow, Alpha0,Alpha1,Alpha2,Alpha3,Alpha4,Alpha5,Alpha6,Alpha7,Alpha8,Alpha9,
        Mouse0, Mouse1, Mouse2, LeftShift, RightShift, LeftControl, RightControl, Tab, Backspace, Delete, F1,F2,F3,F4,F5 }
    public static class Debug { public static void Log(object m){} public static void LogError(object m){} public static void LogWarning(object m){} public static void DrawLine(Vector3 a, Vector3 b){} }
    public static class Physics2D {
        public static Collider2D OverlapCircle(Vector2 p, float r, int mask=0) => null;
        public static Collider2D[] OverlapCircleAll(Vector2 p, float r, int mask=0) => new Collider2D[0];
        public static RaycastHit2D Raycast(Vector2 o, Vector2 d, float dist=float.MaxValue, int mask=0) => new RaycastHit2D();
    }
    public struct RaycastHit2D { public Collider2D collider; public Vector2 point; public static implicit operator bool(RaycastHit2D h) => h.collider != null; }
    public static class PlayerPrefs {
        public static int GetInt(string k, int d=0) => d;
        public static float GetFloat(string k, float d=0f) => d;
        public static string GetString(string k, string d="") => d;
        public static void SetInt(string k, int v){}
        public static void SetFloat(string k, float v){}
        public static void SetString(string k, string v){}
        public static bool HasKey(string k) => false;
        public static void Save(){}
    }
    public interface IDamageable { void TakeDamage(int d); }
    public static class Resources { public static T Load<T>(string p) where T:Object => null; }
}
namespace UnityEngine.UI {
    public class Text : UnityEngine.Component { public string text; public int fontSize; public UnityEngine.Color color; }
    public class Slider : UnityEngine.Component { public float value; public float minValue; public float maxValue; }
    public class Button : UnityEngine.Component { public void onClick_AddListener(System.Action a){} }
    public class Image : UnityEngine.Component { public UnityEngine.Sprite sprite; public UnityEngine.Color color; public float fillAmount; }
    public class Toggle : UnityEngine.Component { public bool isOn; }
    public class InputField : UnityEngine.Component { public string text; }
    public class Canvas : UnityEngine.Component {}
    public class CanvasGroup : UnityEngine.Component { public float alpha; public bool interactable; }
    public class ScrollRect : UnityEngine.Component {}
    public class Dropdown : UnityEngine.Component { public int value; }
}
namespace UnityEngine.SceneManagement {
    public static class SceneManager {
        public static void LoadScene(int i){}
        public static void LoadScene(string n){}
        public static UnityEngine.SceneManagement.Scene GetActiveScene() => new Scene();
    }
    public struct Scene { public string name; public int buildIndex; }
}
namespace UnityEngine.AI {
    public class NavMeshAgent : UnityEngine.Component {
        public float speed; public float stoppingDistance; public bool isStopped;
        public UnityEngine.Vector3 destination;
        public void SetDestination(UnityEngine.Vector3 v){}
        public bool pathPending => false;
        public float remainingDistance => 0f;
    }
}

// ===== Common Game Classes (stubs so cross-script references always compile) =====
public interface IDamageable { void TakeDamage(int d); }

public class GameManager : UnityEngine.MonoBehaviour {
    public static GameManager Instance;
    public int score; public int wave; public bool isGameOver;
    public void OnEnemyKilled() {}
    public void GameOver() {}
    public void SpawnWave() {}
    public void AddScore(int n) {}
}

public class HealthBar : UnityEngine.MonoBehaviour {
    public int maxHealth = 100;
    public UnityEngine.UI.Slider healthSlider;
    public UnityEngine.UI.Text healthText;
    public void TakeDamage(int d) {}
    public void Heal(int h) {}
    public void SetMaxHealth(int m) {}
}

public class PlayerController : UnityEngine.MonoBehaviour {
    public float moveSpeed = 5f;
    public int damage = 10;
    public float shieldStrength = 0f;
    public void TakeDamage(int d) {}
}

public class Shield : UnityEngine.MonoBehaviour {
    public void ActivateShield(int duration) {}
    public void ActivateShield(float duration) {}
}

public class Health : UnityEngine.MonoBehaviour {
    public int maxHealth = 100;
    public void TakeDamage(int d) {}
    public void Heal(int h) {}
}

public class Weapon : UnityEngine.MonoBehaviour {
    public int damage = 10;
    public float fireRate = 1f;
    public void Fire() {}
    public void Upgrade(int level) {}
}

public class RaceManager : UnityEngine.MonoBehaviour {
    public static RaceManager Instance;
    public int totalLaps = 3;
    public void OnCheckpointReached(int playerIndex) {}
    public void OnLapCompleted(int playerIndex) {}
    public void OnRaceFinished(int playerIndex) {}
}

public class CheckpointManager : UnityEngine.MonoBehaviour {
    public static CheckpointManager Instance;
    public void OnCheckpointReached(UnityEngine.GameObject car) {}
}
"""
