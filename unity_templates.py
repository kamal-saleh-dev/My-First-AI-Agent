# unity_templates.py — Unity C# script templates and role definitions
# Edit here without touching agent.py

UNIVERSAL_TEMPLATES = {
    "spawner": """
using UnityEngine;
using System.Collections;
public class {name} : MonoBehaviour
{{
    public GameObject prefabToSpawn;
    public float spawnInterval = 2f;
    public int maxSpawned = 10;
    public Transform[] spawnPoints;
    private int currentCount = 0;
    void Start() {{ StartCoroutine(SpawnLoop()); }}
    IEnumerator SpawnLoop()
    {{
        while (true)
        {{
            yield return new WaitForSeconds(spawnInterval);
            if (currentCount < maxSpawned && prefabToSpawn != null && spawnPoints.Length > 0)
            {{
                Transform sp = spawnPoints[Random.Range(0, spawnPoints.Length)];
                Instantiate(prefabToSpawn, sp.position, Quaternion.identity);
                currentCount++;
            }}
        }}
    }}
    public void OnObjectDestroyed() {{ currentCount = Mathf.Max(0, currentCount - 1); }}
}}""",
    "manager": """
using UnityEngine;
public class {name} : MonoBehaviour
{{
    public static {name} Instance;
    public int score = 0;
    public int wave = 1;
    public bool isGameOver = false;
    public GameObject enemyPrefab;
    public Transform[] spawnPoints;
    private int enemiesAlive = 0;
    void Awake() {{ Instance = this; }}
    void Start() {{ if (spawnPoints.Length > 0 && enemyPrefab != null) SpawnWave(); }}
    public void SpawnWave()
    {{
        int count = wave * 2;
        enemiesAlive = count;
        for (int i = 0; i < count; i++)
            Instantiate(enemyPrefab, spawnPoints[i % spawnPoints.Length].position, Quaternion.identity);
        Debug.Log("Wave " + wave + " | Enemies: " + count);
    }}
    public void OnEnemyKilled()
    {{
        score += 10 * wave;
        enemiesAlive--;
        if (enemiesAlive <= 0) {{ wave++; Invoke(nameof(SpawnWave), 3f); }}
    }}
    public void GameOver()
    {{
        isGameOver = true;
        Time.timeScale = 0f;
        Debug.Log("Game Over! Score: " + score);
    }}
}}""",
    "ui": """
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
public class {name} : MonoBehaviour
{{
    public static {name} Instance;
    public Text scoreText;
    public Text highScoreText;
    public Text livesText;
    public Text timerText;
    public GameObject gameOverPanel;
    public GameObject pausePanel;
    private int score = 0;
    private int lives = 3;
    private float timer = 0f;
    private bool timerRunning = false;
    void Awake() {{ Instance = this; }}
    void Start()
    {{
        if (gameOverPanel != null) gameOverPanel.SetActive(false);
        if (pausePanel != null) pausePanel.SetActive(false);
        UpdateUI();
    }}
    void Update()
    {{
        if (Input.GetKeyDown(KeyCode.Escape)) TogglePause();
        if (timerRunning)
        {{
            timer += Time.deltaTime;
            if (timerText != null) timerText.text = "Time: " + timer.ToString("F1");
        }}
    }}
    public void AddScore(int n)
    {{
        score += n;
        int best = PlayerPrefs.GetInt("HighScore", 0);
        if (score > best) PlayerPrefs.SetInt("HighScore", score);
        UpdateUI();
    }}
    public void LoseLife() {{ lives--; UpdateUI(); if (lives <= 0) ShowGameOver(); }}
    public void StartTimer() {{ timerRunning = true; }}
    public void StopTimer() {{ timerRunning = false; }}
    public void StopTime() {{ StopTimer(); }}
    public float GetTime() {{ return timer; }}
    void UpdateUI()
    {{
        if (scoreText != null) scoreText.text = "Score: " + score;
        if (highScoreText != null) highScoreText.text = "Best: " + PlayerPrefs.GetInt("HighScore", 0);
        if (livesText != null) livesText.text = "Lives: " + lives;
    }}
    public void ShowGameOver() {{ ShowGameOver(""); }}
    public void ShowGameOver(string msg)
    {{
        if (gameOverPanel != null) gameOverPanel.SetActive(true);
        Time.timeScale = 0f;
    }}
    public void RestartGame() {{ Time.timeScale = 1f; SceneManager.LoadScene(0); }}
    void TogglePause()
    {{
        bool p = Time.timeScale == 0f;
        Time.timeScale = p ? 1f : 0f;
        if (pausePanel != null) pausePanel.SetActive(!p);
    }}
}}""",
    "health": """
using UnityEngine;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    public int maxHealth = 100;
    public Slider healthSlider;
    public Text healthText;
    private int currentHealth;
    void Start() {{ currentHealth = maxHealth; UpdateUI(); }}
    public void TakeDamage(int d) {{ currentHealth = Mathf.Max(0, currentHealth - d); UpdateUI(); if (currentHealth <= 0) Die(); }}
    public void Heal(int h) {{ currentHealth = Mathf.Min(maxHealth, currentHealth + h); UpdateUI(); }}
    void UpdateUI()
    {{
        if (healthSlider != null) healthSlider.value = (float)currentHealth / maxHealth;
        if (healthText != null) healthText.text = currentHealth + "/" + maxHealth;
    }}
    void Die()
    {{
        GameManager gm = FindObjectOfType<GameManager>();
        if (gm != null) gm.GameOver();
        gameObject.SetActive(false);
    }}
}}""",
    "background": """
using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float scrollSpeed = 5f;
    public Renderer bgRenderer;
    private Material bgMaterial;
    private float offset = 0f;
    void Start()
    {{
        if (bgRenderer == null) bgRenderer = GetComponent<Renderer>();
        if (bgRenderer != null) bgMaterial = bgRenderer.material;
    }}
    void Update()
    {{
        offset += scrollSpeed * Time.deltaTime * 0.1f;
        if (bgMaterial != null)
            bgMaterial.SetTextureOffset("_MainTex", new Vector2(offset, 0));
    }}
}}""",
    "collectible": """
using UnityEngine;
public class {name} : MonoBehaviour
{{
    public int value = 10;
    public float rotateSpeed = 90f;
    void Update() {{ transform.Rotate(0, rotateSpeed * Time.deltaTime, 0); }}
    void OnTriggerEnter2D(Collider2D other)
    {{
        if (!other.CompareTag("Player")) return;
        GameManager gm = FindObjectOfType<GameManager>();
        if (gm != null) {{ gm.score += value; }}
        Destroy(gameObject);
    }}
}}""",
    "projectile": """
using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float speed = 12f;
    public int damage = 25;
    public float lifetime = 3f;
    private Rigidbody2D rb;
    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        rb.velocity = transform.up * speed;
        Destroy(gameObject, lifetime);
    }}
    void OnTriggerEnter2D(Collider2D other)
    {{
        IDamageable t = other.GetComponent<IDamageable>();
        if (t != null) {{ t.TakeDamage(damage); Destroy(gameObject); }}
        else if (!other.CompareTag("Player")) Destroy(gameObject);
    }}
}}""",

    "gem": """
using UnityEngine;
public class {name} : MonoBehaviour
{{
    public BoardManager boardManager;
    public Vector2Int gridPosition;
    private static Vector2Int? firstSelected = null;

    void OnMouseDown()
    {{
        if (!firstSelected.HasValue)
        {{
            firstSelected = gridPosition;
        }}
        else
        {{
            if (boardManager != null)
                boardManager.SwapGems(firstSelected.Value, gridPosition);
            firstSelected = null;
        }}
    }}
}}""",

    "board": """
using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    public enum GemType {{ Red, Green, Blue, Yellow, Purple }}
    public int gridSizeX = 8;
    public int gridSizeY = 8;
    public GameObject gemPrefab;
    private GemType[,] grid;

    void Start()
    {{
        grid = new GemType[gridSizeX, gridSizeY];
        PopulateBoard();
    }}

    public GemType GemAt(int x, int y)
    {{
        if (x < 0 || x >= gridSizeX || y < 0 || y >= gridSizeY) return GemType.Red;
        return grid[x, y];
    }}

    public Vector3 GetWorldPosition(Vector2Int pos)
    {{
        return new Vector3((pos.x - gridSizeX / 2f) * 1.2f, (pos.y - gridSizeY / 2f) * 1.2f, 0);
    }}

    public void SwapGems(Vector2Int a, Vector2Int b)
    {{
        GemType temp = grid[a.x, a.y];
        grid[a.x, a.y] = grid[b.x, b.y];
        grid[b.x, b.y] = temp;
        GameObject gemA = GameObject.Find($"Gem_{{a.x}}_{{a.y}}");
        GameObject gemB = GameObject.Find($"Gem_{{b.x}}_{{b.y}}");
        if (gemA != null) gemA.transform.position = GetWorldPosition(b);
        if (gemB != null) gemB.transform.position = GetWorldPosition(a);
        CheckForMatches();
    }}

    public void ProcessMatches(List<Vector2Int> positions)
    {{
        foreach (var pos in positions)
        {{
            GameObject g = GameObject.Find($"Gem_{{pos.x}}_{{pos.y}}");
            if (g != null) Destroy(g);
            grid[pos.x, pos.y] = GemType.Red;
        }}
        PopulateBoard();
    }}

    void PopulateBoard()
    {{
        GemType[] types = (GemType[])System.Enum.GetValues(typeof(GemType));
        for (int x = 0; x < gridSizeX; x++)
        {{
            for (int y = 0; y < gridSizeY; y++)
            {{
                if (GameObject.Find($"Gem_{{x}}_{{y}}") != null) continue;
                grid[x, y] = types[Random.Range(0, types.Length)];
                GameObject gem = Instantiate(gemPrefab, GetWorldPosition(new Vector2Int(x, y)), Quaternion.identity);
                gem.name = $"Gem_{{x}}_{{y}}";
                GemScript gs = gem.GetComponent<GemScript>();
                if (gs != null) {{ gs.boardManager = this; gs.gridPosition = new Vector2Int(x, y); }}
            }}
        }}
    }}

    void CheckForMatches()
    {{
        List<Vector2Int> matches = new List<Vector2Int>();
        for (int y = 0; y < gridSizeY; y++)
            for (int x = 0; x <= gridSizeX - 3; x++)
                if (GemAt(x,y) == GemAt(x+1,y) && GemAt(x,y) == GemAt(x+2,y))
                {{ matches.Add(new Vector2Int(x,y)); matches.Add(new Vector2Int(x+1,y)); matches.Add(new Vector2Int(x+2,y)); }}
        for (int x = 0; x < gridSizeX; x++)
            for (int y = 0; y <= gridSizeY - 3; y++)
                if (GemAt(x,y) == GemAt(x,y+1) && GemAt(x,y) == GemAt(x,y+2))
                {{ matches.Add(new Vector2Int(x,y)); matches.Add(new Vector2Int(x,y+1)); matches.Add(new Vector2Int(x,y+2)); }}
        if (matches.Count >= 3) ProcessMatches(matches);
    }}
}}""",

    "powerup": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public enum PowerType {{ Health, Speed, Shield, Score }}
    public PowerType powerType = PowerType.Health;
    public float moveSpeed = 3f;
    public int value = 25;

    void Update()
    {{
        transform.position += Vector3.down * moveSpeed * Time.deltaTime;
        transform.Rotate(0, 0, 90f * Time.deltaTime);
        if (Camera.main != null && transform.position.y < -Camera.main.orthographicSize - 2f)
            Destroy(gameObject);
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (!other.CompareTag("Player")) return;
        ApplyEffect(other.gameObject);
        Destroy(gameObject);
    }}

    void ApplyEffect(GameObject player)
    {{
        switch (powerType)
        {{
            case PowerType.Health:
                HealthBar hb = player.GetComponent<HealthBar>();
                if (hb != null) hb.Heal(value);
                break;
            case PowerType.Speed:
                PlayerController pc = player.GetComponent<PlayerController>();
                if (pc != null) pc.moveSpeed += value;
                break;
            case PowerType.Shield:
                Shield sh = player.GetComponent<Shield>();
                if (sh != null) sh.ActivateShield(value);
                break;
            case PowerType.Score:
                if (GameManager.Instance != null) GameManager.Instance.AddScore(value);
                break;
        }}
    }}
}}""",

    "enemy": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float moveSpeed = 3f;
    public int maxHealth = 50;
    public int damage = 10;
    public float attackRange = 1.5f;
    private int currentHealth;
    private Rigidbody2D rb;
    private Transform player;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        currentHealth = maxHealth;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
    }}

    void Update()
    {{
        if (player == null) {{ rb.velocity = Vector2.down * moveSpeed; return; }}
        float dist = Vector2.Distance(transform.position, player.position);
        if (dist <= attackRange)
        {{
            rb.velocity = Vector2.zero;
            HealthBar hb = player.GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(damage);
        }}
        else
        {{
            Vector2 dir = ((Vector2)player.position - (Vector2)transform.position).normalized;
            rb.velocity = dir * moveSpeed;
        }}
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.OnEnemyKilled();
        Destroy(gameObject);
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (other.CompareTag("Player"))
        {{
            HealthBar hb = other.GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(damage);
        }}
    }}
}}""",

    "player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Movement")]
    public float moveSpeed = 5f;
    public float jumpForce = 8f;
    [Header("Combat")]
    public GameObject bulletPrefab;
    public Transform firePoint;
    public int maxHealth = 100;
    private int currentHealth;
    private Rigidbody2D rb;
    private bool isGrounded;
    private HealthBar healthBar;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        healthBar = GetComponent<HealthBar>();
        currentHealth = maxHealth;
    }}

    void Update()
    {{
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y);
        if (Mathf.Abs(v) > 0.1f && rb.velocity.y == 0f)
            rb.velocity = new Vector2(rb.velocity.x, v * moveSpeed);
        if (Input.GetButtonDown("Jump") && isGrounded)
        {{
            rb.AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);
            isGrounded = false;
        }}
        if (Input.GetButtonDown("Fire1") && bulletPrefab != null && firePoint != null)
            Instantiate(bulletPrefab, firePoint.position, firePoint.rotation);
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        if (col.gameObject.CompareTag("Ground")) isGrounded = true;
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (healthBar != null) healthBar.TakeDamage(dmg);
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.GameOver();
        gameObject.SetActive(false);
    }}
}}""",

    "vehicle": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float enginePower = 500f;
    public float steerSpeed = 150f;
    public float maxSpeed = 15f;
    public float frictionFactor = 0.98f;
    private Rigidbody2D rb;
    private float steerInput;
    private float accelInput;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void Update()
    {{
        steerInput = Input.GetAxis("Horizontal");
        accelInput = Input.GetAxis("Vertical");
    }}

    void FixedUpdate()
    {{
        rb.AddForce(transform.up * enginePower * accelInput * Time.fixedDeltaTime);
        rb.velocity = Vector2.ClampMagnitude(rb.velocity, maxSpeed);
        if (rb.velocity.magnitude > 0.1f)
            rb.rotation -= steerInput * steerSpeed * Time.fixedDeltaTime;
        if (accelInput == 0f)
            rb.velocity *= frictionFactor;
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        if (col.gameObject.CompareTag("Obstacle"))
        {{
            HealthBar hb = GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(10);
        }}
    }}
}}""",

    "opponent": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public Transform[] waypoints;
    public float moveSpeed = 4f;
    private Rigidbody2D rb;
    private int currentWaypoint = 0;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void FixedUpdate()
    {{
        if (waypoints == null || waypoints.Length == 0) return;
        Transform target = waypoints[currentWaypoint];
        Vector2 dir = ((Vector2)target.position - rb.position).normalized;
        rb.velocity = dir * moveSpeed;
        float angle = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f;
        rb.rotation = Mathf.LerpAngle(rb.rotation, angle, Time.fixedDeltaTime * 5f);
        if (Vector2.Distance(rb.position, target.position) < 0.5f)
            currentWaypoint = (currentWaypoint + 1) % waypoints.Length;
    }}
}}""",

    "generic": """using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
public class {name} : MonoBehaviour
{{
    public static {name} Instance;
    public int score = 0;
    public bool isGameOver = false;

    void Awake()
    {{
        if (Instance == null) Instance = this;
        else Destroy(gameObject);
    }}

    void Start() {{ }}

    void Update() {{ }}

    public void AddScore(int n)
    {{
        score += n;
        int best = PlayerPrefs.GetInt("HighScore", 0);
        if (score > best) PlayerPrefs.SetInt("HighScore", score);
    }}

    public void GameOver()
    {{
        isGameOver = true;
        Time.timeScale = 0f;
        Debug.Log("Game Over! Score: " + score);
    }}

    public void RestartGame()
    {{
        Time.timeScale = 1f;
        SceneManager.LoadScene(0);
    }}
}}""",
}

# Roles that use UNIVERSAL_TEMPLATES (full, compilable — NO LLM generation)
TEMPLATED_ROLES = {"spawner", "manager", "ui", "health", "background", "collectible", "projectile", "gem", "board", "powerup", "enemy", "player", "vehicle", "opponent", "generic"}


# Roles that are game-specific → use FILL_TEMPLATES (LLM fills logic sections)
GAME_SPECIFIC_ROLES = {"player", "vehicle", "enemy", "opponent", "powerup", "generic"}

# FILL_TEMPLATES: compilable skeletons with // FILL: markers
# LLM receives the skeleton + task, fills ONLY the marked sections
FILL_TEMPLATES = {
    "player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Movement")]
    public float moveSpeed = 5f;
    public float jumpForce = 8f;
    [Header("Combat")]
    public GameObject bulletPrefab;
    public Transform firePoint;
    public int maxHealth = 100;
    private int currentHealth;
    private Rigidbody2D rb;
    private bool isGrounded;
    private HealthBar healthBar;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        healthBar = GetComponent<HealthBar>();
        currentHealth = maxHealth;
        {fill_start}
    }}

    void Update()
    {{
        {fill_update}
    }}

    void FixedUpdate()
    {{
        {fill_fixed_update}
    }}

    public void TakeDamage(int damage)
    {{
        currentHealth -= damage;
        if (healthBar != null) healthBar.TakeDamage(damage);
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.GameOver();
        gameObject.SetActive(false);
    }}

    {fill_extra}
}}""",

    "enemy": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float moveSpeed = 3f;
    public int maxHealth = 50;
    public int damage = 10;
    public float attackRange = 1.5f;
    private int currentHealth;
    private Rigidbody2D rb;
    private Transform player;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        currentHealth = maxHealth;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
    }}

    void Update()
    {{
        // FILL: enemy behavior — chase player, patrol, fall downward, etc.
        {fill_update}
    }}

    void FixedUpdate()
    {{
        // FILL: physics movement toward player or downward
        {fill_fixed_update}
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.OnEnemyKilled();
        Destroy(gameObject);
    }}

    void AttackPlayer()
    {{
        // FILL: damage player on contact or in range
        {fill_attack}
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (other.CompareTag("Player"))
        {{
            HealthBar hb = other.GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(damage);
        }}
    }}
}}""",

    "vehicle": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float enginePower = 500f;
    public float steerSpeed = 150f;
    public float maxSpeed = 15f;
    public float frictionFactor = 0.98f;
    private Rigidbody2D rb;
    private float steerInput;
    private float accelInput;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void Update()
    {{
        steerInput = Input.GetAxis("Horizontal");
        accelInput = Input.GetAxis("Vertical");
    }}

    void FixedUpdate()
    {{
        rb.AddForce(transform.up * enginePower * accelInput * Time.fixedDeltaTime);
        rb.velocity = Vector2.ClampMagnitude(rb.velocity, maxSpeed);
        if (rb.velocity.magnitude > 0.1f)
            rb.rotation -= steerInput * steerSpeed * Time.fixedDeltaTime;
        if (accelInput == 0f)
            rb.velocity *= frictionFactor;
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        // FILL: handle collision with obstacles, other vehicles, etc.
        {fill_collision}
    }}
}}""",

    "opponent": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public Transform[] waypoints;
    public float moveSpeed = 4f;
    private Rigidbody2D rb;
    private int currentWaypoint = 0;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void FixedUpdate()
    {{
        if (waypoints == null || waypoints.Length == 0) return;
        Transform target = waypoints[currentWaypoint];
        Vector2 dir = ((Vector2)target.position - rb.position).normalized;
        rb.velocity = dir * moveSpeed;
        float angle = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f;
        rb.rotation = Mathf.LerpAngle(rb.rotation, angle, Time.fixedDeltaTime * 5f);
        if (Vector2.Distance(rb.position, target.position) < 0.5f)
            currentWaypoint = (currentWaypoint + 1) % waypoints.Length;
    }}
}}""",

    "powerup": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public enum PowerType {{ Health, Speed, Attack, Shield }}
    public PowerType powerType = PowerType.Health;
    public float moveSpeed = 3f;
    public int value = 25;

    void Update()
    {{
        transform.position += Vector3.down * moveSpeed * Time.deltaTime;
        transform.Rotate(0, 0, 90f * Time.deltaTime);
        if (Camera.main != null && transform.position.y < -Camera.main.orthographicSize - 2f)
            Destroy(gameObject);
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (!other.CompareTag("Player")) return;
        ApplyEffect(other.gameObject);
        Destroy(gameObject);
    }}

    void ApplyEffect(GameObject player)
    {{
        HealthBar hb = player.GetComponent<HealthBar>();
        switch (powerType)
        {{
            case PowerType.Health:
                if (hb != null) hb.Heal(value);
                break;
            case PowerType.Speed:
                var pc = player.GetComponent<PlayerController>();
                if (pc != null) pc.moveSpeed += value;
                break;
            case PowerType.Shield:
                var sh = player.GetComponent<Shield>();
                if (sh != null) sh.ActivateShield(value);
                break;
            case PowerType.Attack:
                if (GameManager.Instance != null) GameManager.Instance.AddScore(value);
                break;
        }}
    }}
}}""",

    "enemy": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float moveSpeed = 3f;
    public int maxHealth = 50;
    public int damage = 10;
    public float attackRange = 1.5f;
    private int currentHealth;
    private Rigidbody2D rb;
    private Transform player;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        currentHealth = maxHealth;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
    }}

    void Update()
    {{
        if (player == null) {{ rb.velocity = Vector2.down * moveSpeed; return; }}
        float dist = Vector2.Distance(transform.position, player.position);
        if (dist <= attackRange)
            AttackPlayer();
        else
        {{
            Vector2 dir = ((Vector2)player.position - (Vector2)transform.position).normalized;
            rb.velocity = dir * moveSpeed;
        }}
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.OnEnemyKilled();
        Destroy(gameObject);
    }}

    void AttackPlayer()
    {{
        rb.velocity = Vector2.zero;
        HealthBar hb = player.GetComponent<HealthBar>();
        if (hb != null) hb.TakeDamage(damage);
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (other.CompareTag("Player"))
        {{
            HealthBar hb = other.GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(damage);
        }}
    }}
}}""",

    "player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Movement")]
    public float moveSpeed = 5f;
    public float jumpForce = 8f;
    [Header("Combat")]
    public GameObject bulletPrefab;
    public Transform firePoint;
    public int maxHealth = 100;
    private int currentHealth;
    private Rigidbody2D rb;
    private bool isGrounded;
    private HealthBar healthBar;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        healthBar = GetComponent<HealthBar>();
        currentHealth = maxHealth;
    }}

    void Update()
    {{
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y != 0 ? rb.velocity.y : v * moveSpeed);

        if (Input.GetButtonDown("Jump") && isGrounded)
        {{
            rb.AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);
            isGrounded = false;
        }}

        if (Input.GetButtonDown("Fire1") && bulletPrefab != null && firePoint != null)
            Instantiate(bulletPrefab, firePoint.position, firePoint.rotation);
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        if (col.gameObject.CompareTag("Ground")) isGrounded = true;
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (healthBar != null) healthBar.TakeDamage(dmg);
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        if (GameManager.Instance != null) GameManager.Instance.GameOver();
        gameObject.SetActive(false);
    }}
}}""",

    "vehicle": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public float enginePower = 500f;
    public float steerSpeed = 150f;
    public float maxSpeed = 15f;
    public float frictionFactor = 0.98f;
    private Rigidbody2D rb;
    private float steerInput;
    private float accelInput;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void Update()
    {{
        steerInput = Input.GetAxis("Horizontal");
        accelInput = Input.GetAxis("Vertical");
    }}

    void FixedUpdate()
    {{
        rb.AddForce(transform.up * enginePower * accelInput * Time.fixedDeltaTime);
        rb.velocity = Vector2.ClampMagnitude(rb.velocity, maxSpeed);
        if (rb.velocity.magnitude > 0.1f)
            rb.rotation -= steerInput * steerSpeed * Time.fixedDeltaTime;
        if (accelInput == 0f)
            rb.velocity *= frictionFactor;
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        if (col.gameObject.CompareTag("Obstacle"))
        {{
            HealthBar hb = GetComponent<HealthBar>();
            if (hb != null) hb.TakeDamage(10);
        }}
    }}
}}""",

    "opponent": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public Transform[] waypoints;
    public float moveSpeed = 4f;
    private Rigidbody2D rb;
    private int currentWaypoint = 0;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    void FixedUpdate()
    {{
        if (waypoints == null || waypoints.Length == 0) return;
        Transform target = waypoints[currentWaypoint];
        Vector2 dir = ((Vector2)target.position - rb.position).normalized;
        rb.velocity = dir * moveSpeed;
        float angle = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f;
        rb.rotation = Mathf.LerpAngle(rb.rotation, angle, Time.fixedDeltaTime * 5f);
        if (Vector2.Distance(rb.position, target.position) < 0.5f)
            currentWaypoint = (currentWaypoint + 1) % waypoints.Length;
    }}
}}""",

    "generic": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // FILL: declare public fields needed for this script
    {fill_fields}

    void Start()
    {{
        // FILL: initialize variables
        {fill_start}
    }}

    void Update()
    {{
        // FILL: per-frame logic
        {fill_update}
    }}

    // FILL: add public methods called by other scripts
    {fill_methods}
}}""",
}

# Role-specific FILL instructions sent to LLM
ROLE_FILL_RULES = {
    "player": """Fill the FILL sections for this game: {task}
- fill_update: read Input.GetAxis / GetButtonDown("Fire1") for this game type. Use GetButtonDown NOT GetButton for shooting.
- fill_fixed_update: apply rb.velocity or rb.AddForce based on movement type
- fill_extra: add Shoot() method if needed — Instantiate(bulletPrefab, firePoint.position, firePoint.rotation)
Return ONLY the completed ```csharp code block with all FILL markers replaced by real code.""",

    "enemy": """Fill the FILL sections for this game: {task}
- fill_update: move toward player (chase) OR fall downward (shooter obstacle) based on game type
- fill_fixed_update: rb.velocity toward player OR Vector2.down * moveSpeed for falling
- fill_attack: if in range, call player HealthBar.TakeDamage(damage)
Return ONLY the completed ```csharp code block with all FILL markers replaced by real code.""",

    "vehicle": """Fill the FILL sections for this game: {task}
- fill_collision: if obstacle tag, take damage; if other vehicle, bounce
Return ONLY the completed ```csharp code block with all FILL markers replaced by real code.""",

    "powerup": """Fill the FILL sections for this game: {task}
- fill_effect: switch on powerType — Health: GetComponent<HealthBar>().Heal(value), Speed: player.GetComponent<PlayerController>().moveSpeed += value, etc.
Return ONLY the completed ```csharp code block with all FILL markers replaced by real code.""",

    "generic": """Fill the FILL sections for this script named {name} in this game: {task}
Analyze the script name and game type to decide what this script should do.
Common patterns:
- BoardManager/GridManager: GemType[,] grid, SwapGems(), ProcessMatches(), GemAt()
- RaceManager/LapManager: lap counter, checkpoint system, winner detection
- InventoryManager: item list, AddItem(), RemoveItem(), display
- QuestManager: quest list, progress tracking, completion check
- DialogManager: dialog queue, ShowDialog(), NextLine()
- AudioManager: Singleton, Play(string), Stop()
- CameraFollow: smooth follow player with offset
- CheckpointManager: checkpoint array, OnCheckpointReached()
- WaveManager (non-spawner): wave counter, score multiplier
- PathFollower: waypoints, MoveTowards, advance index
- fill_fields: declare all needed public/private fields
- fill_start: initialize, find references
- fill_update: per-frame logic
- fill_methods: all public methods other scripts call
Return ONLY the completed ```csharp code block with all FILL markers replaced by real code.""",
}
