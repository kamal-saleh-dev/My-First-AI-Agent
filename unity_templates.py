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
            SpawnEnemy();
        }}
    }}
    public GameObject SpawnEnemy()
    {{
        if (currentCount >= maxSpawned || prefabToSpawn == null || spawnPoints == null || spawnPoints.Length == 0)
            return null;
        Transform sp = spawnPoints[Random.Range(0, spawnPoints.Length)];
        GameObject enemy = Instantiate(prefabToSpawn, sp.position, Quaternion.identity);
        currentCount++;
        return enemy;
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
    void Start() {{ SetMaxHealth(maxHealth); SetHealth(maxHealth); }}
    public void SetMaxHealth(int value)
    {{
        maxHealth = Mathf.Max(1, value);
        if (healthSlider != null)
        {{
            healthSlider.minValue = 0f;
            healthSlider.maxValue = maxHealth;
        }}
        currentHealth = Mathf.Clamp(currentHealth, 0, maxHealth);
        UpdateUI();
    }}
    public void SetHealth(int value)
    {{
        currentHealth = Mathf.Clamp(value, 0, maxHealth);
        UpdateUI();
    }}
    public void TakeDamage(int d) {{ SetHealth(currentHealth - d); if (currentHealth <= 0) Die(); }}
    public void Heal(int h) {{ SetHealth(currentHealth + h); }}
    void UpdateUI()
    {{
        if (healthSlider != null) healthSlider.value = currentHealth;
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
        if (rb != null) rb.velocity = transform.up * speed;
        Destroy(gameObject, lifetime);
    }}
    void OnTriggerEnter2D(Collider2D other)
    {{
        if (other.CompareTag("Player")) return;
        other.SendMessage("TakeDamage", damage, SendMessageOptions.DontRequireReceiver);
        Destroy(gameObject);
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
                ShipController sc = player.GetComponent<ShipController>();
                if (sc == null) sc = player.GetComponent<MonoBehaviour>() as ShipController;
                if (sc != null) sc.moveSpeed += value;
                break;
            case PowerType.Shield:
                // Shield bonus: heal player instead if no Shield component
                HealthBar shHb = player.GetComponent<HealthBar>();
                if (shHb != null) shHb.Heal(value / 2);
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
    private int currentHealth;
    private Rigidbody2D rb;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        currentHealth = maxHealth;
        if (rb != null) rb.velocity = Vector2.down * moveSpeed;
    }}

    void Update()
    {{
        // Destroy when below screen
        if (Camera.main != null)
        {{
            float bottom = Camera.main.transform.position.y - Camera.main.orthographicSize - 1f;
            if (transform.position.y < bottom) Destroy(gameObject);
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
            other.SendMessage("TakeDamage", damage, SendMessageOptions.DontRequireReceiver);
        }}
    }}
}}""",

    "player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Movement")]
    public float moveSpeed = 5f;
    [Header("Combat")]
    public GameObject bulletPrefab;
    public Transform firePoint;
    public int maxHealth = 100;
    private int currentHealth;
    private Rigidbody2D rb;
    private HealthBar healthBar;
    // Camera bounds for clamping
    private float camHalfW;
    private float camHalfH;
    private bool hasCameraBounds;

    void Start()
    {{
        rb = GetComponent<Rigidbody2D>();
        healthBar = GetComponent<HealthBar>();
        currentHealth = maxHealth;
        if (healthBar != null)
        {{
            healthBar.SetMaxHealth(maxHealth);
            healthBar.SetHealth(currentHealth);
        }}
        if (Camera.main != null)
        {{
            camHalfH = Camera.main.orthographicSize;
            camHalfW = camHalfH * Camera.main.aspect;
            hasCameraBounds = true;
        }}
    }}

    void Update()
    {{
        // Full 2D movement — works for shooters, top-down, platformers
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        if (rb != null) rb.velocity = new Vector2(h * moveSpeed, v * moveSpeed);

        // Clamp inside camera bounds
        if (hasCameraBounds)
        {{
            Vector3 pos = transform.position;
            pos.x = Mathf.Clamp(pos.x, -camHalfW + 0.5f, camHalfW - 0.5f);
            pos.y = Mathf.Clamp(pos.y, -camHalfH + 0.5f, camHalfH - 0.5f);
            transform.position = pos;
        }}

        // Shoot
        if (Input.GetButtonDown("Fire1"))
            ShootProjectile();
    }}

    public void ShootProjectile()
    {{
        if (bulletPrefab == null || firePoint == null) return;
        Instantiate(bulletPrefab, firePoint.position, firePoint.rotation);
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth = Mathf.Max(0, currentHealth - dmg);
        if (healthBar != null) healthBar.SetHealth(currentHealth);
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

# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TEMPLATES — Cards, Horror, VR, AR, Simulation, RPG, Fighting, etc.
# ═══════════════════════════════════════════════════════════════════════════════

UNIVERSAL_TEMPLATES.update({

# ─── CARD GAMES ───────────────────────────────────────────────────────────────
    "card": """using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
public class {name} : MonoBehaviour, IPointerClickHandler, IPointerEnterHandler, IPointerExitHandler
{{
    [Header("Card Data")]
    public string cardName;
    public int value;
    public string suit; // Hearts, Diamonds, Clubs, Spades
    public Sprite frontSprite;
    public Sprite backSprite;
    public bool isFaceUp = true;

    private Image cardImage;
    private bool isSelected = false;
    private Vector3 originalPos;
    private CardDeck ownerDeck;

    void Start()
    {{
        cardImage = GetComponent<Image>();
        originalPos = transform.localPosition;
        Refresh();
    }}

    public void Flip()
    {{
        isFaceUp = !isFaceUp;
        Refresh();
    }}

    void Refresh()
    {{
        if (cardImage == null) return;
        cardImage.sprite = isFaceUp ? frontSprite : backSprite;
    }}

    public void OnPointerClick(PointerEventData e)
    {{
        isSelected = !isSelected;
        transform.localPosition = isSelected
            ? originalPos + Vector3.up * 20f
            : originalPos;
    }}

    public void OnPointerEnter(PointerEventData e) {{ transform.localScale = Vector3.one * 1.05f; }}
    public void OnPointerExit(PointerEventData e)  {{ transform.localScale = Vector3.one; }}

    public void SetOwner(CardDeck deck) {{ ownerDeck = deck; }}
}}
""",

    "deck": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Deck Settings")]
    public GameObject cardPrefab;
    public Transform dealPoint;
    public bool shuffleOnStart = true;

    private List<GameObject> cards = new List<GameObject>();
    private List<int> drawPile   = new List<int>();
    private List<int> discardPile = new List<int>();

    // Standard 52-card values and suits
    private static readonly string[] SUITS  = {{"Hearts","Diamonds","Clubs","Spades"}};
    private static readonly string[] VALUES = {{"A","2","3","4","5","6","7","8","9","10","J","Q","K"}};

    void Start()
    {{
        BuildDeck();
        if (shuffleOnStart) Shuffle();
    }}

    void BuildDeck()
    {{
        cards.Clear();
        drawPile.Clear();
        for (int i = 0; i < 52; i++)
        {{
            drawPile.Add(i);
            if (cardPrefab != null)
            {{
                GameObject go = Instantiate(cardPrefab, dealPoint != null ? dealPoint.position : Vector3.zero, Quaternion.identity, transform);
                go.name = $"{{VALUES[i % 13]}}_{{SUITS[i / 13]}}";
                cards.Add(go);
                go.SetActive(false);
            }}
        }}
    }}

    public void Shuffle()
    {{
        for (int i = drawPile.Count - 1; i > 0; i--)
        {{
            int j = Random.Range(0, i + 1);
            int tmp = drawPile[i]; drawPile[i] = drawPile[j]; drawPile[j] = tmp;
        }}
        Debug.Log("Deck shuffled");
    }}

    public GameObject DrawCard()
    {{
        if (drawPile.Count == 0)
        {{
            // Auto-reshuffle discard pile
            drawPile.AddRange(discardPile);
            discardPile.Clear();
            Shuffle();
        }}
        if (drawPile.Count == 0) return null;
        int idx = drawPile[0];
        drawPile.RemoveAt(0);
        discardPile.Add(idx);
        cards[idx].SetActive(true);
        return cards[idx];
    }}

    public void Discard(GameObject card) {{ card.SetActive(false); }}
    public int RemainingCards => drawPile.Count;
}}
""",

    "hand": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Hand Settings")]
    public Transform cardContainer;
    public float cardSpacing = 120f;
    public float fanAngle = 5f;
    public int maxCards = 7;

    private List<GameObject> cardsInHand = new List<GameObject>();

    public bool AddCard(GameObject card)
    {{
        if (cardsInHand.Count >= maxCards) return false;
        cardsInHand.Add(card);
        card.transform.SetParent(cardContainer != null ? cardContainer : transform, false);
        ArrangeCards();
        return true;
    }}

    public void RemoveCard(GameObject card)
    {{
        cardsInHand.Remove(card);
        ArrangeCards();
    }}

    void ArrangeCards()
    {{
        int count = cardsInHand.Count;
        float totalW = (count - 1) * cardSpacing;
        for (int i = 0; i < count; i++)
        {{
            float xPos = -totalW / 2f + i * cardSpacing;
            float angle = fanAngle * ((count / 2f) - i);
            cardsInHand[i].transform.localPosition = new Vector3(xPos, 0f, 0f);
            cardsInHand[i].transform.localRotation = Quaternion.Euler(0f, 0f, angle);
        }}
    }}

    public List<GameObject> GetCards() => cardsInHand;
    public int CardCount => cardsInHand.Count;
}}
""",

# ─── HORROR ───────────────────────────────────────────────────────────────────
    "horror_enemy": """using UnityEngine;
using UnityEngine.AI;
public class {name} : MonoBehaviour
{{
    [Header("AI Settings")]
    public float patrolSpeed   = 1.5f;
    public float chaseSpeed    = 4f;
    public float detectionRange = 10f;
    public float attackRange   = 1.8f;
    public float fieldOfView   = 90f;
    public int   damage        = 25;
    public int   maxHealth     = 100;

    private int currentHealth;
    private NavMeshAgent agent;
    private Transform player;
    private Vector3 patrolTarget;
    private float attackCooldown;

    enum State {{ Patrol, Chase, Attack }}
    private State state = State.Patrol;

    void Start()
    {{
        agent = GetComponent<NavMeshAgent>();
        currentHealth = maxHealth;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
        SetNewPatrolTarget();
    }}

    void Update()
    {{
        if (player == null) return;
        attackCooldown -= Time.deltaTime;
        float dist = Vector3.Distance(transform.position, player.position);

        switch (state)
        {{
            case State.Patrol:
                agent.speed = patrolSpeed;
                if (Vector3.Distance(transform.position, patrolTarget) < 1f) SetNewPatrolTarget();
                if (CanSeePlayer(dist)) state = State.Chase;
                break;

            case State.Chase:
                agent.speed = chaseSpeed;
                agent.SetDestination(player.position);
                if (!CanSeePlayer(dist)) state = State.Patrol;
                if (dist <= attackRange) state = State.Attack;
                break;

            case State.Attack:
                agent.ResetPath();
                if (attackCooldown <= 0f)
                {{
                    attackCooldown = 1.5f;
                    HealthBar hb = player.GetComponent<HealthBar>();
                    if (hb != null) hb.TakeDamage(damage);
                }}
                if (dist > attackRange) state = State.Chase;
                break;
        }}
    }}

    bool CanSeePlayer(float dist)
    {{
        if (dist > detectionRange) return false;
        Vector3 dir = (player.position - transform.position).normalized;
        float angle = Vector3.Angle(transform.forward, dir);
        if (angle > fieldOfView / 2f) return false;
        return !Physics.Raycast(transform.position + Vector3.up, dir, dist, LayerMask.GetMask("Wall","Obstacle"));
    }}

    void SetNewPatrolTarget()
    {{
        patrolTarget = transform.position + new Vector3(Random.Range(-8f,8f), 0f, Random.Range(-8f,8f));
        if (agent != null) agent.SetDestination(patrolTarget);
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) {{ Destroy(gameObject); }}
    }}
}}
""",

    "flashlight": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Flashlight Settings")]
    public Light spotLight;
    public float batteryLife   = 100f;
    public float drainRate     = 2f;     // per second when on
    public float rechargeRate  = 0.5f;   // per second when off
    public bool  isOn          = true;
    public float flickerChance = 0.01f;  // 0–1

    private float battery;

    void Start()
    {{
        battery = batteryLife;
        if (spotLight == null) spotLight = GetComponentInChildren<Light>();
    }}

    void Update()
    {{
        if (Input.GetKeyDown(KeyCode.F)) Toggle();

        if (isOn)
        {{
            battery -= drainRate * Time.deltaTime;
            battery  = Mathf.Clamp(battery, 0f, batteryLife);
            if (battery <= 0f) {{ TurnOff(); return; }}

            // Random flicker
            if (Random.value < flickerChance)
                spotLight.enabled = !spotLight.enabled;
            else
                spotLight.enabled = true;

            // Dim as battery drains
            spotLight.intensity = Mathf.Lerp(0f, 2f, battery / batteryLife);
        }}
        else
        {{
            if (spotLight != null) spotLight.enabled = false;
            battery += rechargeRate * Time.deltaTime;
            battery  = Mathf.Min(battery, batteryLife);
        }}
    }}

    public void Toggle() {{ if (isOn) TurnOff(); else TurnOn(); }}
    void TurnOn()  {{ if (battery > 5f) {{ isOn = true; }} }}
    void TurnOff() {{ isOn = false; }}
    public float BatteryPercent => battery / batteryLife;
}}
""",

    "jumpscare": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Jumpscare")]
    public GameObject scareObject;
    public AudioClip  scareSound;
    public float      displayTime  = 1.5f;
    public float      triggerRange = 2f;
    public bool       oneShot      = true;

    private AudioSource audioSource;
    private bool triggered = false;
    private Transform player;

    void Start()
    {{
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        if (scareObject != null) scareObject.SetActive(false);
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
    }}

    void Update()
    {{
        if (triggered && oneShot) return;
        if (player == null) return;
        if (Vector3.Distance(transform.position, player.position) < triggerRange)
            Trigger();
    }}

    public void Trigger()
    {{
        if (triggered && oneShot) return;
        triggered = true;
        if (scareObject != null) scareObject.SetActive(true);
        if (scareSound  != null) audioSource.PlayOneShot(scareSound);
        Invoke(nameof(Hide), displayTime);
    }}

    void Hide()
    {{
        if (scareObject != null) scareObject.SetActive(false);
        if (!oneShot) triggered = false;
    }}
}}
""",

# ─── VR ───────────────────────────────────────────────────────────────────────
    "vr_player": """using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.Interaction.Toolkit;
public class {name} : MonoBehaviour
{{
    [Header("VR Settings")]
    public Transform     cameraRig;
    public Transform     leftHand;
    public Transform     rightHand;
    public float         moveSpeed = 2f;
    public float         snapTurnAngle = 45f;
    public CharacterController charController;

    private InputDevice leftController;
    private InputDevice rightController;
    private bool snapCooldown = false;

    void Start()
    {{
        charController = GetComponent<CharacterController>();
        InitControllers();
    }}

    void InitControllers()
    {{
        var left  = new System.Collections.Generic.List<InputDevice>();
        var right = new System.Collections.Generic.List<InputDevice>();
        InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Left  | InputDeviceCharacteristics.Controller, left);
        InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Right | InputDeviceCharacteristics.Controller, right);
        if (left.Count  > 0) leftController  = left[0];
        if (right.Count > 0) rightController = right[0];
    }}

    void Update()
    {{
        HandleLocomotion();
        HandleSnapTurn();
        if (!leftController.isValid || !rightController.isValid) InitControllers();
    }}

    void HandleLocomotion()
    {{
        if (!leftController.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 axis)) return;
        if (axis.magnitude < 0.1f) return;
        Vector3 dir = cameraRig.TransformDirection(new Vector3(axis.x, 0f, axis.y));
        dir.y = 0f;
        charController.SimpleMove(dir * moveSpeed);
    }}

    void HandleSnapTurn()
    {{
        if (!rightController.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 axis)) return;
        if (Mathf.Abs(axis.x) > 0.7f && !snapCooldown)
        {{
            transform.Rotate(0f, Mathf.Sign(axis.x) * snapTurnAngle, 0f);
            snapCooldown = true;
            Invoke(nameof(ResetSnap), 0.3f);
        }}
        if (Mathf.Abs(axis.x) < 0.3f) snapCooldown = false;
    }}

    void ResetSnap() {{ snapCooldown = false; }}
}}
""",

    "vr_grab": """using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
[RequireComponent(typeof(XRGrabInteractable))]
public class {name} : MonoBehaviour
{{
    [Header("Grab Settings")]
    public float throwMultiplier = 1.5f;
    public bool  snapToHand      = true;
    public Vector3 holdOffset    = Vector3.zero;
    public Vector3 holdRotation  = Vector3.zero;

    private XRGrabInteractable grabInteractable;
    private Rigidbody rb;
    private bool isGrabbed;

    void Awake()
    {{
        grabInteractable = GetComponent<XRGrabInteractable>();
        rb = GetComponent<Rigidbody>();

        grabInteractable.selectEntered.AddListener(OnGrab);
        grabInteractable.selectExited.AddListener(OnRelease);

        if (snapToHand)
        {{
            grabInteractable.attachTransform = transform;
        }}
    }}

    void OnGrab(SelectEnterEventArgs args)
    {{
        isGrabbed = true;
        rb.useGravity = false;
        transform.localPosition = holdOffset;
        transform.localEulerAngles = holdRotation;
    }}

    void OnRelease(SelectExitEventArgs args)
    {{
        isGrabbed = false;
        rb.useGravity = true;
        // Amplify throw velocity
        rb.velocity        *= throwMultiplier;
        rb.angularVelocity *= throwMultiplier;
    }}
}}
""",

# ─── AR ───────────────────────────────────────────────────────────────────────
    "ar_manager": """using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using System.Collections.Generic;
[RequireComponent(typeof(ARRaycastManager))]
[RequireComponent(typeof(ARPlaneManager))]
public class {name} : MonoBehaviour
{{
    [Header("AR Settings")]
    public GameObject objectToPlace;
    public bool       allowMultiple = false;

    private ARRaycastManager  raycastManager;
    private ARPlaneManager    planeManager;
    private List<ARRaycastHit> hits = new List<ARRaycastHit>();
    private GameObject        spawnedObject;
    private bool              placed = false;

    void Awake()
    {{
        raycastManager = GetComponent<ARRaycastManager>();
        planeManager   = GetComponent<ARPlaneManager>();
    }}

    void Update()
    {{
        if (placed && !allowMultiple) return;
        if (Input.touchCount == 0) return;
        Touch touch = Input.GetTouch(0);
        if (touch.phase != TouchPhase.Began) return;

        if (raycastManager.Raycast(touch.position, hits, TrackableType.PlaneWithinPolygon))
        {{
            Pose hitPose = hits[0].pose;

            if (spawnedObject == null)
                spawnedObject = Instantiate(objectToPlace, hitPose.position, hitPose.rotation);
            else
            {{
                spawnedObject.transform.position = hitPose.position;
                spawnedObject.transform.rotation = hitPose.rotation;
            }}
            placed = true;
        }}
    }}

    public void TogglePlanes(bool visible)
    {{
        foreach (var plane in planeManager.trackables)
            plane.gameObject.SetActive(visible);
    }}

    public void ResetPlacement()
    {{
        if (spawnedObject != null) Destroy(spawnedObject);
        placed = false;
    }}
}}
""",

# ─── SIMULATION ───────────────────────────────────────────────────────────────
    "day_night": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Time Settings")]
    public float dayDurationSeconds = 120f; // real seconds per game day
    public float startHour          = 8f;
    [Range(0,24)] public float currentHour = 8f;

    [Header("Sun")]
    public Light sunLight;
    public Gradient sunColor;
    public AnimationCurve sunIntensity;

    [Header("Ambient")]
    public Gradient ambientColor;
    public Color nightFogColor   = new Color(0.05f,0.05f,0.1f);
    public Color dayFogColor     = new Color(0.7f,0.8f,0.9f);
    public bool  enableFog       = true;

    void Start()
    {{
        currentHour = startHour;
        RenderSettings.fog = enableFog;
    }}

    void Update()
    {{
        currentHour += (24f / dayDurationSeconds) * Time.deltaTime;
        if (currentHour >= 24f) currentHour -= 24f;

        float t = currentHour / 24f;
        float sunAngle = (t * 360f) - 90f;

        if (sunLight != null)
        {{
            sunLight.transform.rotation = Quaternion.Euler(sunAngle, -30f, 0f);
            sunLight.color     = sunColor.Evaluate(t);
            sunLight.intensity = sunIntensity.Evaluate(t);
        }}

        RenderSettings.ambientLight = ambientColor.Evaluate(t);
        if (enableFog)
            RenderSettings.fogColor = Color.Lerp(nightFogColor, dayFogColor, sunIntensity.Evaluate(t));
    }}

    public bool IsNight => currentHour < 6f || currentHour > 20f;
    public bool IsDay   => !IsNight;
}}
""",

    "weather": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Weather Systems")]
    public ParticleSystem rainParticles;
    public ParticleSystem snowParticles;
    public ParticleSystem fogParticles;
    public Light          sunLight;

    [Header("Transition")]
    public float transitionSpeed = 0.5f;

    public enum WeatherType {{ Clear, Rain, Snow, Fog, Storm }}
    public WeatherType currentWeather = WeatherType.Clear;

    private float targetRain, targetSnow, targetFog, targetSunIntensity;
    private float currentRain, currentSnow, currentFog;

    void Start() {{ ApplyWeather(currentWeather); }}

    void Update()
    {{
        currentRain = Mathf.MoveTowards(currentRain, targetRain, transitionSpeed * Time.deltaTime);
        currentSnow = Mathf.MoveTowards(currentSnow, targetSnow, transitionSpeed * Time.deltaTime);
        currentFog  = Mathf.MoveTowards(currentFog,  targetFog,  transitionSpeed * Time.deltaTime);

        SetParticleEmission(rainParticles, currentRain);
        SetParticleEmission(snowParticles, currentSnow);
        SetParticleEmission(fogParticles,  currentFog);

        if (sunLight != null)
            sunLight.intensity = Mathf.MoveTowards(sunLight.intensity, targetSunIntensity, transitionSpeed * Time.deltaTime);

        RenderSettings.fogDensity = currentFog * 0.05f;
    }}

    public void SetWeather(WeatherType weather) {{ currentWeather = weather; ApplyWeather(weather); }}

    void ApplyWeather(WeatherType w)
    {{
        targetRain = targetSnow = targetFog = 0f;
        switch (w)
        {{
            case WeatherType.Clear:  targetSunIntensity = 1.2f; break;
            case WeatherType.Rain:   targetRain = 500f; targetSunIntensity = 0.3f; break;
            case WeatherType.Snow:   targetSnow = 300f; targetSunIntensity = 0.5f; break;
            case WeatherType.Fog:    targetFog  = 200f; targetSunIntensity = 0.4f; break;
            case WeatherType.Storm:  targetRain = 1000f; targetSunIntensity = 0.1f; break;
        }}
    }}

    void SetParticleEmission(ParticleSystem ps, float rate)
    {{
        if (ps == null) return;
        var em = ps.emission;
        em.rateOverTime = rate;
        if (rate > 0f && !ps.isPlaying) ps.Play();
        else if (rate <= 0f && ps.isPlaying) ps.Stop();
    }}
}}
""",

    "physics_sim": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Physics Object")]
    public float mass          = 1f;
    public float drag          = 0.5f;
    public float angularDrag   = 0.5f;
    public bool  useGravity    = true;
    public bool  isKinematic   = false;
    public PhysicMaterial physicMaterial;

    [Header("Interaction")]
    public bool  canPickUp     = true;
    public bool  isDestructible = false;
    public int   durability    = 100;
    public GameObject destroyEffect;

    private Rigidbody rb;
    private Collider col;
    private int currentDurability;

    void Awake()
    {{
        rb = GetComponent<Rigidbody>();
        col = GetComponent<Collider>();
        if (rb == null) rb = gameObject.AddComponent<Rigidbody>();

        rb.mass        = mass;
        rb.drag        = drag;
        rb.angularDrag = angularDrag;
        rb.useGravity  = useGravity;
        rb.isKinematic = isKinematic;
        if (physicMaterial != null && col != null) col.material = physicMaterial;

        currentDurability = durability;
    }}

    void OnCollisionEnter(Collision col)
    {{
        if (!isDestructible) return;
        float impact = col.relativeVelocity.magnitude;
        if (impact > 3f)
        {{
            int dmg = Mathf.RoundToInt(impact * 5f);
            currentDurability -= dmg;
            if (currentDurability <= 0) Break();
        }}
    }}

    void Break()
    {{
        if (destroyEffect != null)
            Instantiate(destroyEffect, transform.position, Quaternion.identity);
        Destroy(gameObject);
    }}

    public void ApplyForce(Vector3 force, ForceMode mode = ForceMode.Impulse)
    {{
        if (rb != null && !rb.isKinematic) rb.AddForce(force, mode);
    }}
}}
""",

# ─── RPG SYSTEMS ──────────────────────────────────────────────────────────────
    "inventory": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Inventory Settings")]
    public int maxSlots = 20;

    [System.Serializable]
    public class Item
    {{
        public string itemName;
        public string description;
        public Sprite icon;
        public int    quantity;
        public bool   isStackable;
        public int    maxStack = 99;
        public enum ItemType {{ Weapon, Armor, Consumable, Quest, Material }}
        public ItemType type;
    }}

    private List<Item> items = new List<Item>();
    public static {name} Instance {{ get; private set; }}

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
    }}

    public bool AddItem(Item newItem)
    {{
        if (newItem.isStackable)
        {{
            Item existing = items.Find(i => i.itemName == newItem.itemName);
            if (existing != null)
            {{
                int space = existing.maxStack - existing.quantity;
                int add   = Mathf.Min(space, newItem.quantity);
                existing.quantity += add;
                return true;
            }}
        }}
        if (items.Count >= maxSlots) return false;
        items.Add(newItem);
        return true;
    }}

    public bool RemoveItem(string itemName, int qty = 1)
    {{
        Item item = items.Find(i => i.itemName == itemName);
        if (item == null) return false;
        item.quantity -= qty;
        if (item.quantity <= 0) items.Remove(item);
        return true;
    }}

    public bool HasItem(string itemName, int qty = 1)
    {{
        Item item = items.Find(i => i.itemName == itemName);
        return item != null && item.quantity >= qty;
    }}

    public List<Item> GetItems() => new List<Item>(items);
    public int ItemCount => items.Count;
}}
""",

    "dialogue": """using UnityEngine;
using UnityEngine.UI;
using System.Collections;
public class {name} : MonoBehaviour
{{
    [Header("UI References")]
    public GameObject dialoguePanel;
    public Text       speakerNameText;
    public Text       dialogueText;
    public Button     nextButton;
    public float      typingSpeed = 0.03f;

    [System.Serializable]
    public class DialogueLine
    {{
        public string speaker;
        [TextArea(2,4)]
        public string text;
        public AudioClip voice;
    }}

    [Header("Dialogue")]
    public DialogueLine[] lines;

    private int currentLine = 0;
    private bool isTyping   = false;
    private Coroutine typingCoroutine;
    private AudioSource audioSource;

    void Start()
    {{
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        if (dialoguePanel != null) dialoguePanel.SetActive(false);
        if (nextButton != null) nextButton.onClick.AddListener(OnNext);
    }}

    public void StartDialogue()
    {{
        currentLine = 0;
        if (dialoguePanel != null) dialoguePanel.SetActive(true);
        ShowLine();
    }}

    void ShowLine()
    {{
        if (currentLine >= lines.Length) {{ EndDialogue(); return; }}
        DialogueLine line = lines[currentLine];
        if (speakerNameText != null) speakerNameText.text = line.speaker;
        if (line.voice != null) audioSource.PlayOneShot(line.voice);
        if (typingCoroutine != null) StopCoroutine(typingCoroutine);
        typingCoroutine = StartCoroutine(TypeText(line.text));
    }}

    IEnumerator TypeText(string text)
    {{
        isTyping = true;
        if (dialogueText != null) dialogueText.text = "";
        foreach (char c in text)
        {{
            if (dialogueText != null) dialogueText.text += c;
            yield return new WaitForSeconds(typingSpeed);
        }}
        isTyping = false;
    }}

    void OnNext()
    {{
        if (isTyping)
        {{
            if (typingCoroutine != null) StopCoroutine(typingCoroutine);
            if (dialogueText != null) dialogueText.text = lines[currentLine].text;
            isTyping = false;
        }}
        else
        {{
            currentLine++;
            ShowLine();
        }}
    }}

    void EndDialogue()
    {{
        if (dialoguePanel != null) dialoguePanel.SetActive(false);
    }}
}}
""",

    "quest": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [System.Serializable]
    public class Quest
    {{
        public string id;
        public string title;
        public string description;
        public int    rewardGold;
        public int    rewardXP;
        public enum State {{ Available, Active, Completed, Failed }}
        public State state = State.Available;

        [System.Serializable]
        public class Objective
        {{
            public string description;
            public int    required;
            public int    current;
            public bool   IsComplete => current >= required;
            public void   Progress(int amt = 1) {{ current = Mathf.Min(current + amt, required); }}
        }}
        public Objective[] objectives;
        public bool AllObjectivesComplete {{ get {{
            foreach (var o in objectives) if (!o.IsComplete) return false; return true;
        }} }}
    }}

    public static {name} Instance {{ get; private set; }}
    private List<Quest> quests = new List<Quest>();

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
    }}

    public void AcceptQuest(string id)
    {{
        Quest q = quests.Find(x => x.id == id && x.state == Quest.State.Available);
        if (q != null) q.state = Quest.State.Active;
    }}

    public void ProgressObjective(string questId, int objectiveIndex, int amount = 1)
    {{
        Quest q = quests.Find(x => x.id == questId && x.state == Quest.State.Active);
        if (q == null || objectiveIndex >= q.objectives.Length) return;
        q.objectives[objectiveIndex].Progress(amount);
        if (q.AllObjectivesComplete) CompleteQuest(questId);
    }}

    public void CompleteQuest(string id)
    {{
        Quest q = quests.Find(x => x.id == id);
        if (q != null)
        {{
            q.state = Quest.State.Completed;
            Debug.Log($"Quest complete: {{q.title}} — +{{q.rewardGold}} gold, +{{q.rewardXP}} XP");
        }}
    }}

    public void AddQuest(Quest q) {{ quests.Add(q); }}
    public List<Quest> ActiveQuests => quests.FindAll(q => q.state == Quest.State.Active);
    public List<Quest> AllQuests    => new List<Quest>(quests);
}}
""",

    "save_system": """using UnityEngine;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    private string savePath;

    [System.Serializable]
    public class SaveData
    {{
        public float   playerX, playerY, playerZ;
        public int     health, score, level;
        public float   playTime;
        public string  currentScene;
        public bool[]  achievements;
    }}

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
        savePath = Path.Combine(Application.persistentDataPath, "save.dat");
    }}

    public void Save(SaveData data)
    {{
        try
        {{
            BinaryFormatter bf = new BinaryFormatter();
            using (FileStream fs = File.Create(savePath))
                bf.Serialize(fs, data);
            Debug.Log($"Game saved to {{savePath}}");
        }}
        catch (System.Exception e) {{ Debug.LogError($"Save failed: {{e.Message}}"); }}
    }}

    public SaveData Load()
    {{
        if (!File.Exists(savePath)) return null;
        try
        {{
            BinaryFormatter bf = new BinaryFormatter();
            using (FileStream fs = File.Open(savePath, FileMode.Open))
                return (SaveData)bf.Deserialize(fs);
        }}
        catch (System.Exception e) {{ Debug.LogError($"Load failed: {{e.Message}}"); return null; }}
    }}

    public bool HasSave() => File.Exists(savePath);
    public void DeleteSave() {{ if (File.Exists(savePath)) File.Delete(savePath); }}
}}
""",

# ─── UTILITY SYSTEMS ──────────────────────────────────────────────────────────
    "audio_manager": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}

    [Header("Audio Sources")]
    public AudioSource musicSource;
    public AudioSource sfxSource;
    public AudioSource ambientSource;

    [Header("Default Clips")]
    public AudioClip defaultMusic;
    public AudioClip defaultAmbient;

    [Range(0,1)] public float masterVolume = 1f;
    [Range(0,1)] public float musicVolume  = 0.7f;
    [Range(0,1)] public float sfxVolume    = 1f;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else {{ Destroy(gameObject); return; }}
        SetupSources();
    }}

    void SetupSources()
    {{
        if (musicSource   == null) {{ musicSource   = gameObject.AddComponent<AudioSource>(); musicSource.loop   = true; }}
        if (sfxSource     == null) {{ sfxSource     = gameObject.AddComponent<AudioSource>(); }}
        if (ambientSource == null) {{ ambientSource = gameObject.AddComponent<AudioSource>(); ambientSource.loop = true; }}
        ApplyVolumes();
        if (defaultMusic   != null) PlayMusic(defaultMusic);
        if (defaultAmbient != null) PlayAmbient(defaultAmbient);
    }}

    public void PlayMusic(AudioClip clip, bool fade = false)
    {{
        musicSource.clip = clip;
        musicSource.Play();
    }}

    public void PlaySFX(AudioClip clip, float pitchVariance = 0f)
    {{
        if (clip == null) return;
        sfxSource.pitch = 1f + Random.Range(-pitchVariance, pitchVariance);
        sfxSource.PlayOneShot(clip, sfxVolume * masterVolume);
    }}

    public void PlaySFXAt(AudioClip clip, Vector3 pos, float vol = 1f)
    {{
        AudioSource.PlayClipAtPoint(clip, pos, vol * sfxVolume * masterVolume);
    }}

    public void PlayAmbient(AudioClip clip) {{ ambientSource.clip = clip; ambientSource.Play(); }}
    public void StopMusic()   {{ musicSource.Stop(); }}
    public void StopAmbient() {{ ambientSource.Stop(); }}

    public void SetMasterVolume(float v) {{ masterVolume = v; ApplyVolumes(); }}
    public void SetMusicVolume(float v)  {{ musicVolume  = v; ApplyVolumes(); }}
    public void SetSFXVolume(float v)    {{ sfxVolume    = v; ApplyVolumes(); }}

    void ApplyVolumes()
    {{
        if (musicSource   != null) musicSource.volume   = musicVolume   * masterVolume;
        if (ambientSource != null) ambientSource.volume = 0.5f          * masterVolume;
    }}
}}
""",

    "camera_controller": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Follow Settings")]
    public Transform target;
    public Vector3   offset         = new Vector3(0f, 5f, -10f);
    public float     followSpeed    = 5f;
    public float     lookSpeed      = 3f;
    public bool      smoothFollow   = true;

    [Header("Orbit (Right-click drag)")]
    public bool  enableOrbit      = false;
    public float orbitSensitivity = 2f;
    private float orbitX, orbitY;

    [Header("Zoom")]
    public bool  enableZoom   = true;
    public float zoomSpeed    = 3f;
    public float minZoom      = 2f;
    public float maxZoom      = 20f;
    private float currentZoom = 10f;

    [Header("Screen Shake")]
    private Vector3 shakeOffset;
    private float   shakeDuration;
    private float   shakeMagnitude;

    void LateUpdate()
    {{
        if (target == null) return;

        // Zoom
        if (enableZoom)
        {{
            currentZoom -= Input.GetAxis("Mouse ScrollWheel") * zoomSpeed;
            currentZoom  = Mathf.Clamp(currentZoom, minZoom, maxZoom);
            offset        = offset.normalized * currentZoom;
        }}

        // Orbit
        if (enableOrbit && Input.GetMouseButton(1))
        {{
            orbitX += Input.GetAxis("Mouse X") * orbitSensitivity;
            orbitY -= Input.GetAxis("Mouse Y") * orbitSensitivity;
            orbitY  = Mathf.Clamp(orbitY, -30f, 80f);
        }}

        // Screen shake
        if (shakeDuration > 0f)
        {{
            shakeOffset    = Random.insideUnitSphere * shakeMagnitude;
            shakeDuration -= Time.deltaTime;
        }} else shakeOffset = Vector3.zero;

        Quaternion rot     = Quaternion.Euler(orbitY, orbitX, 0f);
        Vector3    desiredPos = target.position + rot * offset + shakeOffset;

        transform.position = smoothFollow
            ? Vector3.Lerp(transform.position, desiredPos, followSpeed * Time.deltaTime)
            : desiredPos;
        transform.LookAt(target.position + Vector3.up * 1f);
    }}

    public void Shake(float duration, float magnitude)
    {{
        shakeDuration  = duration;
        shakeMagnitude = magnitude;
    }}
}}
""",

    "touch_input": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Touch Settings")]
    public float tapMaxDuration   = 0.2f;
    public float swipeMinDistance = 50f;
    public float pinchSensitivity = 0.01f;

    public event System.Action<Vector2>         OnTap;
    public event System.Action<Vector2>         OnSwipe;
    public event System.Action<float>           OnPinch;    // delta scale
    public event System.Action<Vector2, float>  OnDrag;     // pos, delta

    private Vector2 touchStart;
    private float   touchTime;
    private bool    isSwiping;

    void Update()
    {{
        if (Input.touchCount == 1) HandleSingleTouch();
        if (Input.touchCount == 2) HandlePinch();

        // Mouse fallback for editor
        #if UNITY_EDITOR
        HandleMouseFallback();
        #endif
    }}

    void HandleSingleTouch()
    {{
        Touch t = Input.GetTouch(0);
        switch (t.phase)
        {{
            case TouchPhase.Began:
                touchStart = t.position; touchTime = Time.time; isSwiping = false; break;
            case TouchPhase.Moved:
                if (t.deltaPosition.magnitude > 5f)
                {{
                    isSwiping = true;
                    OnDrag?.Invoke(t.position, t.deltaPosition);
                }}
                break;
            case TouchPhase.Ended:
                float dur  = Time.time - touchTime;
                float dist = Vector2.Distance(t.position, touchStart);
                if (!isSwiping && dur < tapMaxDuration)
                    OnTap?.Invoke(t.position);
                else if (dist > swipeMinDistance)
                    OnSwipe?.Invoke((t.position - touchStart).normalized);
                break;
        }}
    }}

    void HandlePinch()
    {{
        Touch t0 = Input.GetTouch(0), t1 = Input.GetTouch(1);
        float prevDist = Vector2.Distance(t0.position - t0.deltaPosition, t1.position - t1.deltaPosition);
        float currDist = Vector2.Distance(t0.position, t1.position);
        OnPinch?.Invoke((currDist - prevDist) * pinchSensitivity);
    }}

    void HandleMouseFallback()
    {{
        if (Input.GetMouseButtonDown(0)) touchStart = Input.mousePosition;
        if (Input.GetMouseButton(0))
            OnDrag?.Invoke(Input.mousePosition, new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 10f);
        if (Input.GetMouseButtonUp(0))
        {{
            float dist = Vector2.Distance(Input.mousePosition, touchStart);
            if (dist < swipeMinDistance) OnTap?.Invoke(Input.mousePosition);
        }}
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 0.01f) OnPinch?.Invoke(scroll);
    }}
}}
""",

    "pathfinding": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Simple grid-based A* pathfinding (no NavMesh dependency)
    [Header("Grid Settings")]
    public LayerMask obstacleLayer;
    public float     nodeSize    = 1f;
    public int       gridWidth   = 20;
    public int       gridHeight  = 20;

    private bool[,] walkable;

    void Start() {{ BuildGrid(); }}

    void BuildGrid()
    {{
        walkable = new bool[gridWidth, gridHeight];
        Vector3 origin = transform.position - new Vector3(gridWidth * nodeSize / 2f, 0f, gridHeight * nodeSize / 2f);
        for (int x = 0; x < gridWidth; x++)
        for (int z = 0; z < gridHeight; z++)
        {{
            Vector3 worldPos = origin + new Vector3(x * nodeSize + nodeSize/2f, 0.5f, z * nodeSize + nodeSize/2f);
            walkable[x,z] = !Physics.CheckSphere(worldPos, nodeSize * 0.4f, obstacleLayer);
        }}
    }}

    public List<Vector3> FindPath(Vector3 startWorld, Vector3 endWorld)
    {{
        Vector3 origin = transform.position - new Vector3(gridWidth * nodeSize / 2f, 0f, gridHeight * nodeSize / 2f);
        Vector2Int start = WorldToGrid(startWorld, origin);
        Vector2Int end   = WorldToGrid(endWorld,   origin);

        if (!InBounds(start) || !InBounds(end) || !walkable[end.x, end.y]) return new List<Vector3>();

        // A* implementation
        var open   = new List<Node>() {{ new Node(start, null, 0, Heuristic(start, end)) }};
        var closed = new HashSet<Vector2Int>();

        while (open.Count > 0)
        {{
            open.Sort((a,b) => a.f.CompareTo(b.f));
            Node current = open[0]; open.RemoveAt(0);
            if (current.pos == end) return ReconstructPath(current, origin);
            closed.Add(current.pos);

            foreach (Vector2Int nb in GetNeighbors(current.pos))
            {{
                if (closed.Contains(nb) || !walkable[nb.x, nb.y]) continue;
                float g = current.g + 1f;
                Node  nbNode = new Node(nb, current, g, g + Heuristic(nb, end));
                if (!open.Exists(n => n.pos == nb && n.g <= g)) open.Add(nbNode);
            }}
        }}
        return new List<Vector3>();
    }}

    List<Vector3> ReconstructPath(Node end, Vector3 origin)
    {{
        var path = new List<Vector3>();
        for (Node n = end; n != null; n = n.parent)
            path.Insert(0, origin + new Vector3(n.pos.x * nodeSize + nodeSize/2f, 0f, n.pos.y * nodeSize + nodeSize/2f));
        return path;
    }}

    IEnumerable<Vector2Int> GetNeighbors(Vector2Int p)
    {{
        int[] dx = {{-1,1,0,0}}; int[] dz = {{0,0,-1,1}};
        for (int i = 0; i < 4; i++)
        {{
            var nb = new Vector2Int(p.x + dx[i], p.y + dz[i]);
            if (InBounds(nb)) yield return nb;
        }}
    }}

    bool InBounds(Vector2Int p) => p.x >= 0 && p.x < gridWidth && p.y >= 0 && p.y < gridHeight;
    float Heuristic(Vector2Int a, Vector2Int b) => Mathf.Abs(a.x-b.x) + Mathf.Abs(a.y-b.y);
    Vector2Int WorldToGrid(Vector3 world, Vector3 origin) =>
        new Vector2Int(Mathf.FloorToInt((world.x - origin.x) / nodeSize), Mathf.FloorToInt((world.z - origin.z) / nodeSize));

    class Node {{ public Vector2Int pos; public Node parent; public float g, h, f;
        public Node(Vector2Int p, Node par, float g, float f) {{ pos=p; parent=par; this.g=g; this.f=f; }} }}
}}
""",

    "minimap": """using UnityEngine;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    [Header("Minimap Settings")]
    public Camera    minimapCamera;
    public RawImage  minimapDisplay;
    public Transform player;
    public float     height      = 30f;
    public float     size        = 15f;
    public bool      rotateWithPlayer = true;

    private RenderTexture renderTex;

    void Start()
    {{
        renderTex = new RenderTexture(256, 256, 16);
        if (minimapCamera != null)
        {{
            minimapCamera.targetTexture = renderTex;
            minimapCamera.orthographic  = true;
            minimapCamera.orthographicSize = size;
        }}
        if (minimapDisplay != null) minimapDisplay.texture = renderTex;
    }}

    void LateUpdate()
    {{
        if (player == null || minimapCamera == null) return;
        minimapCamera.transform.position = player.position + Vector3.up * height;
        if (rotateWithPlayer)
            minimapCamera.transform.rotation = Quaternion.Euler(90f, player.eulerAngles.y, 0f);
        else
            minimapCamera.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
    }}

    public void SetSize(float newSize) {{ size = newSize; if (minimapCamera != null) minimapCamera.orthographicSize = size; }}
}}
""",

    "interaction": """using UnityEngine;
using UnityEngine.UI;
[RequireComponent(typeof(Collider))]
public class {name} : MonoBehaviour
{{
    [Header("Interaction Settings")]
    public string  interactKey   = "E";
    public float   interactRange = 2.5f;
    public string  promptText    = "Press E to interact";
    public Text    promptUI;

    private bool   playerInRange = false;
    private Transform player;

    public event System.Action OnInteract;
    public event System.Action OnEnter;
    public event System.Action OnExit;

    void Start()
    {{
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
        if (promptUI != null) promptUI.gameObject.SetActive(false);
    }}

    void Update()
    {{
        if (player == null) return;
        bool inRange = Vector3.Distance(transform.position, player.position) <= interactRange;

        if (inRange && !playerInRange)
        {{
            playerInRange = true;
            if (promptUI != null) {{ promptUI.text = promptText; promptUI.gameObject.SetActive(true); }}
            OnEnter?.Invoke();
        }}
        else if (!inRange && playerInRange)
        {{
            playerInRange = false;
            if (promptUI != null) promptUI.gameObject.SetActive(false);
            OnExit?.Invoke();
        }}

        if (playerInRange && Input.GetKeyDown(interactKey))
            OnInteract?.Invoke();
    }}
}}
""",

    "scene_manager": """using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}

    [Header("Transition")]
    public Image  fadePanel;
    public float  fadeDuration = 0.5f;
    private bool  isLoading   = false;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
    }}

    public void LoadScene(string sceneName)
    {{
        if (!isLoading) StartCoroutine(LoadWithFade(sceneName));
    }}

    public void LoadScene(int index)
    {{
        if (!isLoading) StartCoroutine(LoadWithFade(index));
    }}

    public void ReloadCurrent() => LoadScene(SceneManager.GetActiveScene().buildIndex);
    public void LoadNext()      => LoadScene(SceneManager.GetActiveScene().buildIndex + 1);
    public void LoadMain()      => LoadScene(0);

    IEnumerator LoadWithFade(object scene)
    {{
        isLoading = true;
        yield return StartCoroutine(Fade(1f));
        AsyncOperation op = scene is string s
            ? SceneManager.LoadSceneAsync(s)
            : SceneManager.LoadSceneAsync((int)scene);
        while (!op.isDone) yield return null;
        yield return StartCoroutine(Fade(0f));
        isLoading = false;
    }}

    IEnumerator Fade(float target)
    {{
        if (fadePanel == null) yield break;
        float start = fadePanel.color.a;
        for (float t = 0f; t < fadeDuration; t += Time.unscaledDeltaTime)
        {{
            float a = Mathf.Lerp(start, target, t / fadeDuration);
            fadePanel.color = new Color(0f, 0f, 0f, a);
            yield return null;
        }}
        fadePanel.color = new Color(0f, 0f, 0f, target);
    }}

    public string CurrentScene => SceneManager.GetActiveScene().name;
}}
""",

    "leaderboard": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}

    [System.Serializable]
    public class Entry
    {{
        public string playerName;
        public int    score;
        public string date;
        public Entry(string n, int s) {{ playerName = n; score = s; date = System.DateTime.Now.ToShortDateString(); }}
    }}

    private List<Entry> entries = new List<Entry>();
    private const string SAVE_KEY = "Leaderboard";
    private const int MAX_ENTRIES = 10;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else {{ Destroy(gameObject); return; }}
        Load();
    }}

    public void SubmitScore(string playerName, int score)
    {{
        entries.Add(new Entry(playerName, score));
        entries.Sort((a,b) => b.score.CompareTo(a.score));
        if (entries.Count > MAX_ENTRIES) entries.RemoveRange(MAX_ENTRIES, entries.Count - MAX_ENTRIES);
        Save();
    }}

    public List<Entry> GetTopEntries(int count = 10) =>
        entries.GetRange(0, Mathf.Min(count, entries.Count));

    public int GetRank(int score)
    {{
        int rank = 1;
        foreach (var e in entries) {{ if (e.score > score) rank++; }}
        return rank;
    }}

    void Save()
    {{
        var wrapper = new EntriesWrapper {{ entries = entries };
        PlayerPrefs.SetString(SAVE_KEY, JsonUtility.ToJson(wrapper));
    }}

    void Load()
    {{
        string json = PlayerPrefs.GetString(SAVE_KEY, "");
        if (!string.IsNullOrEmpty(json))
        {{
            var wrapper = JsonUtility.FromJson<EntriesWrapper>(json);
            if (wrapper != null) entries = wrapper.entries;
        }}
    }}

    [System.Serializable] class EntriesWrapper {{ public List<Entry> entries; }}
}}
""",

    "state_machine": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Generic State Machine — works for any game (RPG, horror, fighting, etc.)
    public abstract class State
    {{
        protected {name} machine;
        public State({name} m) {{ machine = m; }}
        public virtual void Enter()  {{ }}
        public virtual void Update() {{ }}
        public virtual void Exit()   {{ }}
    }}

    private State currentState;
    private Dictionary<string, State> states = new Dictionary<string, State>();

    public string CurrentStateName {{ get; private set; }} = "None";

    public void RegisterState(string name, State state) {{ states[name] = state; }}

    public void ChangeState(string name)
    {{
        if (!states.ContainsKey(name))
        {{ Debug.LogWarning($"State '{{name}}' not found!"); return; }}
        currentState?.Exit();
        CurrentStateName = name;
        currentState = states[name];
        currentState.Enter();
    }}

    void Update() {{ currentState?.Update(); }}
}}
""",

    "npc": """using UnityEngine;
using UnityEngine.AI;
public class {name} : MonoBehaviour
{{
    [Header("NPC Settings")]
    public string   npcName      = "NPC";
    public float    walkSpeed    = 1.5f;
    public float    talkRange    = 2f;
    public Transform[] waypoints;
    public bool     loopWaypoints = true;

    [Header("Dialogue")]
    public string[] greetings    = {{"Hello!", "Hi there!"}};

    private NavMeshAgent  agent;
    private int           waypointIndex = 0;
    private bool          isTalking     = false;
    private Transform     player;

    void Start()
    {{
        agent  = GetComponent<NavMeshAgent>();
        agent.speed = walkSpeed;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
        if (waypoints.Length > 0) agent.SetDestination(waypoints[0].position);
    }}

    void Update()
    {{
        if (player != null && Vector3.Distance(transform.position, player.position) < talkRange)
        {{
            FaceTarget(player.position);
            if (!isTalking) {{ isTalking = true; Greet(); }}
            return;
        }}
        isTalking = false;
        Patrol();
    }}

    void Patrol()
    {{
        if (waypoints.Length == 0 || agent == null) return;
        if (agent.remainingDistance < 0.5f && !agent.pathPending)
        {{
            waypointIndex = (waypointIndex + 1) % waypoints.Length;
            agent.SetDestination(waypoints[waypointIndex].position);
        }}
    }}

    void FaceTarget(Vector3 target)
    {{
        Vector3 dir = (target - transform.position);
        dir.y = 0f;
        if (dir != Vector3.zero)
            transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(dir), 5f * Time.deltaTime);
    }}

    void Greet()
    {{
        if (greetings.Length == 0) return;
        string msg = greetings[Random.Range(0, greetings.Length)];
        Debug.Log($"{{npcName}}: {{msg}}");
    }}

    public void Talk(string message) {{ Debug.Log($"{{npcName}}: {{message}}"); }}
}}
""",

    "procedural_map": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Map Settings")]
    public int    width          = 50;
    public int    height         = 50;
    public float  wallThreshold  = 0.45f;
    public int    smoothPasses   = 5;
    public int    seed           = 0;
    public bool   randomSeed     = true;

    [Header("Prefabs")]
    public GameObject wallPrefab;
    public GameObject floorPrefab;
    public GameObject playerSpawnPrefab;

    private int[,] map;

    void Start() {{ GenerateMap(); }}

    public void GenerateMap()
    {{
        if (randomSeed) seed = Random.Range(0, 99999);
        System.Random rng = new System.Random(seed);
        map = new int[width, height];

        // Random fill
        for (int x = 0; x < width; x++)
        for (int y = 0; y < height; y++)
            map[x,y] = (x == 0 || x == width-1 || y == 0 || y == height-1)
                ? 1 : (rng.NextDouble() < wallThreshold ? 1 : 0);

        // Smooth with cellular automata
        for (int i = 0; i < smoothPasses; i++) Smooth();

        SpawnTiles();
    }}

    void Smooth()
    {{
        int[,] newMap = (int[,])map.Clone();
        for (int x = 1; x < width-1; x++)
        for (int y = 1; y < height-1; y++)
        {{
            int neighbors = 0;
            for (int nx = x-1; nx <= x+1; nx++)
            for (int ny = y-1; ny <= y+1; ny++)
                if (nx != x || ny != y) neighbors += map[nx, ny];
            newMap[x, y] = neighbors > 4 ? 1 : 0;
        }}
        map = newMap;
    }}

    void SpawnTiles()
    {{
        // Clear existing children
        foreach (Transform child in transform) Destroy(child.gameObject);

        bool spawnedPlayer = false;
        for (int x = 0; x < width; x++)
        for (int y = 0; y < height; y++)
        {{
            Vector3 pos = new Vector3(x, 0f, y);
            GameObject prefab = map[x, y] == 1 ? wallPrefab : floorPrefab;
            if (prefab != null) Instantiate(prefab, pos, Quaternion.identity, transform);
            if (!spawnedPlayer && map[x,y] == 0 && playerSpawnPrefab != null)
            {{
                Instantiate(playerSpawnPrefab, pos + Vector3.up, Quaternion.identity);
                spawnedPlayer = true;
            }}
        }}
    }}

    public bool IsWalkable(int x, int y) =>
        x >= 0 && x < width && y >= 0 && y < height && map[x,y] == 0;
}}
""",

    "object_pool": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Object Pool — reuse GameObjects instead of Instantiate/Destroy
    // Huge performance win for bullets, particles, enemies, etc.
    public static {name} Instance {{ get; private set; }}

    [System.Serializable]
    public class Pool
    {{
        public string       tag;
        public GameObject   prefab;
        public int          initialSize = 10;
    }}

    public List<Pool> pools;
    private Dictionary<string, Queue<GameObject>> poolDict = new Dictionary<string, Queue<GameObject>>();

    void Awake()
    {{
        if (Instance == null) Instance = this; else Destroy(gameObject);
    }}

    void Start()
    {{
        foreach (Pool p in pools)
        {{
            var q = new Queue<GameObject>();
            for (int i = 0; i < p.initialSize; i++)
            {{
                GameObject go = Instantiate(p.prefab, transform);
                go.SetActive(false);
                q.Enqueue(go);
            }}
            poolDict[p.tag] = q;
        }}
    }}

    public GameObject Get(string tag, Vector3 pos, Quaternion rot)
    {{
        if (!poolDict.ContainsKey(tag))
        {{ Debug.LogWarning($"Pool '{{tag}}' not found!"); return null; }}

        Queue<GameObject> q = poolDict[tag];
        if (q.Count == 0)
        {{
            // Expand pool
            Pool pool = pools.Find(p => p.tag == tag);
            if (pool == null) return null;
            GameObject extra = Instantiate(pool.prefab, transform);
            extra.SetActive(false);
            q.Enqueue(extra);
        }}

        GameObject obj = q.Dequeue();
        obj.transform.SetPositionAndRotation(pos, rot);
        obj.SetActive(true);
        return obj;
    }}

    public void Return(string tag, GameObject obj)
    {{
        obj.SetActive(false);
        obj.transform.SetParent(transform);
        if (poolDict.ContainsKey(tag)) poolDict[tag].Enqueue(obj);
    }}
}}
""",

    "timer": """using UnityEngine;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    [Header("Timer Settings")]
    public float  duration      = 60f;
    public bool   countDown     = true;
    public bool   autoStart     = true;
    public Text   timerText;

    private float currentTime;
    private bool  isRunning = false;

    public event System.Action OnTimerEnd;
    public event System.Action<float> OnTick;

    void Start()
    {{
        currentTime = countDown ? duration : 0f;
        if (autoStart) StartTimer();
    }}

    void Update()
    {{
        if (!isRunning) return;
        currentTime += (countDown ? -1f : 1f) * Time.deltaTime;
        OnTick?.Invoke(currentTime);
        UpdateUI();
        if (countDown && currentTime <= 0f)   {{ currentTime = 0f; End(); }}
        if (!countDown && currentTime >= duration) End();
    }}

    void UpdateUI()
    {{
        if (timerText == null) return;
        int mins = Mathf.FloorToInt(Mathf.Abs(currentTime) / 60f);
        int secs = Mathf.FloorToInt(Mathf.Abs(currentTime) % 60f);
        timerText.text = $"{{mins:00}}:{{secs:00}}";
    }}

    public void StartTimer()  {{ isRunning = true; }}
    public void PauseTimer()  {{ isRunning = false; }}
    public void ResetTimer()  {{ currentTime = countDown ? duration : 0f; isRunning = false; }}
    public void RestartTimer(){{ currentTime = countDown ? duration : 0f; isRunning = true; }}
    void End() {{ isRunning = false; OnTimerEnd?.Invoke(); }}
    public float TimeRemaining => countDown ? currentTime : duration - currentTime;
    public bool  IsRunning     => isRunning;
}}
""",

    "ragdoll": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Ragdoll toggler — attach to character root
    private Rigidbody[]  bodies;
    private Collider[]   cols;
    private Animator     animator;
    private bool         isRagdolling = false;

    void Awake()
    {{
        bodies   = GetComponentsInChildren<Rigidbody>();
        cols     = GetComponentsInChildren<Collider>();
        animator = GetComponent<Animator>();
        SetRagdoll(false);
    }}

    public void SetRagdoll(bool enable)
    {{
        isRagdolling = enable;
        foreach (var rb in bodies)
        {{
            rb.isKinematic = !enable;
            rb.useGravity  = enable;
        }}
        foreach (var col in cols)
            if (!col.isTrigger) col.enabled = enable;
        if (animator != null) animator.enabled = !enable;
    }}

    public void Die(Vector3 force = default, Vector3 forcePoint = default)
    {{
        SetRagdoll(true);
        if (force != Vector3.zero)
        {{
            Rigidbody hitRb = GetComponentInChildren<Rigidbody>();
            if (hitRb != null) hitRb.AddForceAtPosition(force, forcePoint == Vector3.zero ? transform.position : forcePoint, ForceMode.Impulse);
        }}
    }}

    public bool IsRagdolling => isRagdolling;
}}
""",

    "hyper_casual": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Hyper-casual one-touch controller (tap/hold to move)
    [Header("Hyper Casual Settings")]
    public float   moveSpeed     = 6f;
    public float   jumpForce     = 8f;
    public bool    autoRun       = true;
    public bool    tapToJump     = true;
    public float   laneWidth     = 2f;
    public int     lanes         = 3;
    public float   laneSwipeThreshold = 50f;

    private int    currentLane   = 1; // 0=left, 1=center, 2=right
    private float  targetX;
    private Rigidbody rb;
    private bool   isGrounded;
    private Vector2 swipeStart;

    void Start()
    {{
        rb = GetComponent<Rigidbody>();
        targetX = GetLaneX(currentLane);
    }}

    void Update()
    {{
        // Auto-run forward
        if (autoRun) rb.velocity = new Vector3(rb.velocity.x, rb.velocity.y, moveSpeed);

        // Smooth lane movement
        Vector3 pos = transform.position;
        pos.x = Mathf.Lerp(pos.x, targetX, 10f * Time.deltaTime);
        transform.position = pos;

        HandleInput();
    }}

    void HandleInput()
    {{
        // Touch
        if (Input.touchCount > 0)
        {{
            Touch t = Input.GetTouch(0);
            if (t.phase == TouchPhase.Began) swipeStart = t.position;
            if (t.phase == TouchPhase.Ended)
            {{
                float dx = t.position.x - swipeStart.x;
                float dy = t.position.y - swipeStart.y;
                if (Mathf.Abs(dx) > laneSwipeThreshold)
                    ChangeLane(dx > 0 ? 1 : -1);
                else if (tapToJump && Mathf.Abs(dx) < laneSwipeThreshold/2f)
                    Jump();
            }}
        }}

        // Keyboard fallback
        if (Input.GetKeyDown(KeyCode.LeftArrow)  || Input.GetKeyDown(KeyCode.A)) ChangeLane(-1);
        if (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.D)) ChangeLane(1);
        if (Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.UpArrow)) Jump();
    }}

    void ChangeLane(int dir)
    {{
        currentLane = Mathf.Clamp(currentLane + dir, 0, lanes - 1);
        targetX = GetLaneX(currentLane);
    }}

    float GetLaneX(int lane) => (lane - (lanes - 1) / 2f) * laneWidth;

    void Jump()
    {{
        if (!isGrounded) return;
        rb.AddForce(Vector3.up * jumpForce, ForceMode.Impulse);
        isGrounded = false;
    }}

    void OnCollisionEnter(Collision col)
    {{
        if (col.gameObject.CompareTag("Ground")) isGrounded = true;
    }}
}}
""",

    "fighting": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Fighting game controller (Street Fighter style)
    [Header("Fighter Settings")]
    public float moveSpeed   = 4f;
    public float jumpForce   = 10f;
    public int   maxHealth   = 100;
    public float attackRange = 1.5f;
    public int   punchDamage = 10;
    public int   kickDamage  = 15;

    private int    currentHealth;
    private bool   isGrounded;
    private bool   isBlocking;
    private float  attackCooldown;
    private Rigidbody2D rb;
    private Animator    anim;
    private {name}      opponent;

    void Start()
    {{
        rb   = GetComponent<Rigidbody2D>();
        anim = GetComponent<Animator>();
        currentHealth = maxHealth;
        // Find opponent (other fighter)
        foreach (var f in FindObjectsOfType<{name}>())
            if (f != this) {{ opponent = f; break; }}
    }}

    void Update()
    {{
        attackCooldown -= Time.deltaTime;
        HandleMovement();
        HandleCombat();
    }}

    void HandleMovement()
    {{
        float h = Input.GetAxisRaw("Horizontal");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y);
        isBlocking = Input.GetKey(KeyCode.LeftControl);

        if (Input.GetKeyDown(KeyCode.Space) && isGrounded)
        {{
            rb.AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);
            isGrounded = false;
        }}
        // Face opponent
        if (opponent != null)
        {{
            float dir = opponent.transform.position.x - transform.position.x;
            transform.localScale = new Vector3(dir > 0 ? 1 : -1, 1, 1);
        }}
    }}

    void HandleCombat()
    {{
        if (attackCooldown > 0f) return;
        if (Input.GetKeyDown(KeyCode.Z)) Attack(punchDamage, 0.4f, "Punch");
        if (Input.GetKeyDown(KeyCode.X)) Attack(kickDamage,  0.6f, "Kick");
    }}

    void Attack(int dmg, float cd, string animTrigger)
    {{
        attackCooldown = cd;
        if (anim != null) anim.SetTrigger(animTrigger);
        if (opponent == null) return;
        float dist = Vector2.Distance(transform.position, opponent.transform.position);
        if (dist <= attackRange) opponent.TakeDamage(dmg);
    }}

    public void TakeDamage(int dmg)
    {{
        if (isBlocking) dmg = Mathf.Max(1, dmg / 3);
        currentHealth = Mathf.Max(0, currentHealth - dmg);
        if (anim != null) anim.SetTrigger("Hit");
        if (currentHealth <= 0) KO();
    }}

    void KO()
    {{
        if (anim != null) anim.SetTrigger("KO");
        rb.simulated = false;
        Debug.Log($"{{gameObject.name}} KO!");
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{ if (col.gameObject.CompareTag("Ground")) isGrounded = true; }}

    public float HealthPercent => (float)currentHealth / maxHealth;
}}
""",

})


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TEMPLATES 2 — Puzzle, Tower Defense, Strategy, Sports, Rhythm, etc.
# ═══════════════════════════════════════════════════════════════════════════════

UNIVERSAL_TEMPLATES.update({

# ─── PUZZLE SYSTEMS ───────────────────────────────────────────────────────────
    "puzzle_grid": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Grid Settings")]
    public int    cols        = 8;
    public int    rows        = 8;
    public float  cellSize    = 1f;
    public GameObject cellPrefab;

    protected GameObject[,] grid;
    protected int[,]         values;

    public event System.Action<int,int> OnCellClicked;
    public event System.Action          OnBoardChanged;

    protected virtual void Start()
    {{
        grid   = new GameObject[cols, rows];
        values = new int[cols, rows];
        BuildGrid();
    }}

    protected virtual void BuildGrid()
    {{
        Vector3 origin = transform.position - new Vector3(cols * cellSize / 2f - cellSize / 2f, rows * cellSize / 2f - cellSize / 2f, 0f);
        for (int x = 0; x < cols; x++)
        for (int y = 0; y < rows; y++)
        {{
            if (cellPrefab == null) continue;
            Vector3 pos = origin + new Vector3(x * cellSize, y * cellSize, 0f);
            GameObject cell = Instantiate(cellPrefab, pos, Quaternion.identity, transform);
            cell.name = $"Cell_{{x}}_{{y}}";
            grid[x, y] = cell;
            int cx = x, cy = y;
            var btn = cell.GetComponent<UnityEngine.UI.Button>();
            if (btn != null) btn.onClick.AddListener(() => HandleCellClick(cx, cy));
        }}
    }}

    protected virtual void HandleCellClick(int x, int y)
    {{
        OnCellClicked?.Invoke(x, y);
    }}

    public bool InBounds(int x, int y) => x >= 0 && x < cols && y >= 0 && y < rows;

    public void SetValue(int x, int y, int v)
    {{
        if (!InBounds(x,y)) return;
        values[x,y] = v;
        OnBoardChanged?.Invoke();
    }}

    public int GetValue(int x, int y) => InBounds(x,y) ? values[x,y] : -1;

    public void ClearBoard()
    {{
        for (int x = 0; x < cols; x++)
        for (int y = 0; y < rows; y++)
            values[x,y] = 0;
        OnBoardChanged?.Invoke();
    }}
}}
""",

    "match3": """using UnityEngine;
using System.Collections;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Match-3 Settings")]
    public int     cols        = 8;
    public int     rows        = 8;
    public int     gemTypes    = 6;
    public GameObject[] gemPrefabs;
    public float   swapDuration  = 0.2f;
    public float   fallDuration  = 0.15f;
    public int     scorePerGem   = 10;

    private GameObject[,] board;
    private int[,]         types;
    private int            score;
    private bool           isProcessing;

    void Start() {{ StartCoroutine(InitBoard()); }}

    IEnumerator InitBoard()
    {{
        board = new GameObject[cols, rows];
        types = new int[cols, rows];
        for (int x = 0; x < cols; x++)
        for (int y = 0; y < rows; y++)
        {{
            SpawnGem(x, y, Random.Range(0, gemTypes));
            yield return null;
        }}
        // Ensure no initial matches
        while (FindMatches().Count > 0)
        {{
            foreach (var m in FindMatches())
                types[m.x, m.y] = Random.Range(0, gemTypes);
        }}
    }}

    void SpawnGem(int x, int y, int type)
    {{
        if (gemPrefabs == null || gemPrefabs.Length == 0) return;
        int t = Mathf.Clamp(type, 0, gemPrefabs.Length - 1);
        Vector3 pos = GridToWorld(x, y);
        if (board[x,y] != null) Destroy(board[x,y]);
        board[x,y] = Instantiate(gemPrefabs[t], pos, Quaternion.identity, transform);
        types[x,y] = t;
    }}

    public IEnumerator TrySwap(int x1, int y1, int x2, int y2)
    {{
        if (isProcessing) yield break;
        isProcessing = true;
        Swap(x1,y1,x2,y2);
        yield return new WaitForSeconds(swapDuration);
        var matches = FindMatches();
        if (matches.Count == 0)
        {{
            Swap(x2,y2,x1,y1); // revert
        }}
        else
        {{
            yield return StartCoroutine(ResolveMatches(matches));
        }}
        isProcessing = false;
    }}

    void Swap(int x1, int y1, int x2, int y2)
    {{
        (types[x1,y1], types[x2,y2]) = (types[x2,y2], types[x1,y1]);
        (board[x1,y1], board[x2,y2]) = (board[x2,y2], board[x1,y1]);
        if (board[x1,y1]) board[x1,y1].transform.position = GridToWorld(x1,y1);
        if (board[x2,y2]) board[x2,y2].transform.position = GridToWorld(x2,y2);
    }}

    List<Vector2Int> FindMatches()
    {{
        var matched = new HashSet<Vector2Int>();
        for (int x = 0; x < cols; x++) for (int y = 0; y < rows-2; y++) {{ if (types[x,y]==types[x,y+1]&&types[x,y]==types[x,y+2]) for(int i=0;i<3;i++) matched.Add(new Vector2Int(x,y+i)); }}
        for (int y = 0; y < rows; y++) for (int x = 0; x < cols-2; x++) {{ if (types[x,y]==types[x+1,y]&&types[x,y]==types[x+2,y]) for(int i=0;i<3;i++) matched.Add(new Vector2Int(x+i,y)); }}
        return new List<Vector2Int>(matched);
    }}

    IEnumerator ResolveMatches(List<Vector2Int> matches)
    {{
        score += matches.Count * scorePerGem;
        foreach (var m in matches) {{ if(board[m.x,m.y]!=null) Destroy(board[m.x,m.y]); board[m.x,m.y]=null; }}
        yield return new WaitForSeconds(0.2f);
        yield return StartCoroutine(FillBoard());
        var newMatches = FindMatches();
        if (newMatches.Count > 0) yield return StartCoroutine(ResolveMatches(newMatches));
    }}

    IEnumerator FillBoard()
    {{
        for (int x = 0; x < cols; x++)
        {{
            for (int y = 0; y < rows; y++)
            {{
                if (board[x,y] == null)
                {{
                    SpawnGem(x, y, Random.Range(0, gemTypes));
                    yield return new WaitForSeconds(fallDuration * 0.1f);
                }}
            }}
        }}
    }}

    Vector3 GridToWorld(int x, int y) => transform.position + new Vector3(x - cols/2f + 0.5f, y - rows/2f + 0.5f, 0f);
    public int Score => score;
}}
""",

    "sokoban": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Sokoban / box-pushing puzzle
    [Header("Level")]
    public TextAsset levelData;  // '#'=wall, 'P'=player, 'B'=box, 'G'=goal, '.'=floor
    public GameObject wallPrefab, floorPrefab, boxPrefab, goalPrefab, playerPrefab;
    public float cellSize = 1f;

    private char[,] levelMap;
    private GameObject playerObj;
    private Vector2Int playerPos;
    private List<GameObject> boxes = new List<GameObject>();
    private List<Vector2Int> boxPositions = new List<Vector2Int>();
    private List<Vector2Int> goalPositions = new List<Vector2Int>();
    private int cols, rows;

    void Start() {{ LoadLevel(); }}

    void LoadLevel()
    {{
        if (levelData == null) return;
        string[] lines = levelData.text.Split('
');
        rows = lines.Length; cols = 0;
        foreach (var l in lines) cols = Mathf.Max(cols, l.TrimEnd().Length);
        levelMap = new char[cols, rows];
        for (int y = 0; y < rows; y++)
        {{
            string line = y < lines.Length ? lines[y].TrimEnd() : "";
            for (int x = 0; x < cols; x++)
            {{
                char c = x < line.Length ? line[x] : ' ';
                levelMap[x, rows-1-y] = c;
                Vector3 pos = new Vector3(x * cellSize, (rows-1-y) * cellSize, 0f);
                switch (c)
                {{
                    case '#': if(wallPrefab)  Instantiate(wallPrefab,  pos, Quaternion.identity, transform); break;
                    case '.': if(floorPrefab) Instantiate(floorPrefab, pos, Quaternion.identity, transform); break;
                    case 'G': goalPositions.Add(new Vector2Int(x, rows-1-y)); if(goalPrefab) Instantiate(goalPrefab, pos, Quaternion.identity, transform); break;
                    case 'P': playerPos = new Vector2Int(x, rows-1-y); if(playerPrefab) playerObj = Instantiate(playerPrefab, pos, Quaternion.identity); break;
                    case 'B': boxPositions.Add(new Vector2Int(x, rows-1-y)); if(boxPrefab) boxes.Add(Instantiate(boxPrefab, pos, Quaternion.identity, transform)); break;
                }}
            }}
        }}
    }}

    void Update()
    {{
        Vector2Int dir = Vector2Int.zero;
        if (Input.GetKeyDown(KeyCode.W) || Input.GetKeyDown(KeyCode.UpArrow))    dir = Vector2Int.up;
        if (Input.GetKeyDown(KeyCode.S) || Input.GetKeyDown(KeyCode.DownArrow))  dir = Vector2Int.down;
        if (Input.GetKeyDown(KeyCode.A) || Input.GetKeyDown(KeyCode.LeftArrow))  dir = Vector2Int.left;
        if (Input.GetKeyDown(KeyCode.D) || Input.GetKeyDown(KeyCode.RightArrow)) dir = Vector2Int.right;
        if (dir != Vector2Int.zero) TryMove(dir);
    }}

    void TryMove(Vector2Int dir)
    {{
        Vector2Int next = playerPos + dir;
        if (!IsWalkable(next)) return;
        int boxIdx = boxPositions.IndexOf(next);
        if (boxIdx >= 0)
        {{
            Vector2Int boxNext = next + dir;
            if (!IsWalkable(boxNext) || boxPositions.Contains(boxNext)) return;
            boxPositions[boxIdx] = boxNext;
            boxes[boxIdx].transform.position = GridToWorld(boxNext);
        }}
        playerPos = next;
        if (playerObj != null) playerObj.transform.position = GridToWorld(next);
        if (CheckWin()) Debug.Log("Level Complete!");
    }}

    bool IsWalkable(Vector2Int p) => p.x>=0&&p.x<cols&&p.y>=0&&p.y<rows && levelMap[p.x,p.y]!='#';
    bool CheckWin() {{ foreach(var bp in boxPositions) if (!goalPositions.Contains(bp)) return false; return goalPositions.Count > 0; }}
    Vector3 GridToWorld(Vector2Int p) => new Vector3(p.x * cellSize, p.y * cellSize, 0f);
}}
""",

    "sliding_puzzle": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Sliding (15-puzzle) controller
    [Header("Puzzle Settings")]
    public int    size         = 4;   // 4x4 = 15 puzzle, 3x3 = 8 puzzle
    public float  cellSize     = 1.5f;
    public float  slideSpeed   = 8f;
    public int    shuffleMoves = 100;

    private int[,]         board;
    private Vector2Int     emptyPos;
    private bool           isSolved;
    private Dictionary<int, Transform> pieces = new Dictionary<int, Transform>();
    private bool isSliding = false;

    public event System.Action OnSolved;

    void Start()
    {{
        board = new int[size, size];
        InitBoard();
        Shuffle(shuffleMoves);
    }}

    void InitBoard()
    {{
        int n = 0;
        for (int y = size-1; y >= 0; y--)
        for (int x = 0; x < size; x++)
        {{
            board[x,y] = n;
            n++;
        }}
        emptyPos = new Vector2Int(size-1, 0); // last cell = empty
    }}

    void Shuffle(int moves)
    {{
        Vector2Int[] dirs = {{ Vector2Int.up, Vector2Int.down, Vector2Int.left, Vector2Int.right }};
        Vector2Int lastDir = Vector2Int.zero;
        for (int i = 0; i < moves; i++)
        {{
            var valid = new List<Vector2Int>();
            foreach (var d in dirs)
            {{
                if (d == -lastDir) continue; // no backtrack
                Vector2Int nb = emptyPos + d;
                if (nb.x>=0&&nb.x<size&&nb.y>=0&&nb.y<size) valid.Add(d);
            }}
            if (valid.Count == 0) continue;
            var chosen = valid[Random.Range(0, valid.Count)];
            SlideImmediate(emptyPos + chosen);
            lastDir = chosen;
        }}
    }}

    void SlideImmediate(Vector2Int tilePos)
    {{
        board[emptyPos.x, emptyPos.y] = board[tilePos.x, tilePos.y];
        board[tilePos.x, tilePos.y]   = 0;
        emptyPos = tilePos;
    }}

    void Update()
    {{
        if (isSliding || isSolved) return;
        if (Input.GetMouseButtonDown(0))
        {{
            Vector3 wp = Camera.main.ScreenToWorldPoint(Input.mousePosition);
            int cx = Mathf.RoundToInt((wp.x + (size-1)*cellSize/2f) / cellSize);
            int cy = Mathf.RoundToInt((wp.y + (size-1)*cellSize/2f) / cellSize);
            TrySlide(new Vector2Int(cx, cy));
        }}
    }}

    void TrySlide(Vector2Int tilePos)
    {{
        if (!InBounds(tilePos)) return;
        Vector2Int diff = tilePos - emptyPos;
        if (Mathf.Abs(diff.x) + Mathf.Abs(diff.y) != 1) return;
        StartCoroutine(AnimateSlide(tilePos));
    }}

    System.Collections.IEnumerator AnimateSlide(Vector2Int tilePos)
    {{
        isSliding = true;
        int tileVal = board[tilePos.x, tilePos.y];
        if (pieces.ContainsKey(tileVal))
        {{
            Transform t = pieces[tileVal];
            Vector3 target = GridToWorld(emptyPos);
            while (Vector3.Distance(t.position, target) > 0.01f)
            {{
                t.position = Vector3.MoveTowards(t.position, target, slideSpeed * Time.deltaTime);
                yield return null;
            }}
            t.position = target;
        }}
        SlideImmediate(tilePos);
        isSliding = false;
        if (CheckSolved()) {{ isSolved = true; OnSolved?.Invoke(); Debug.Log("Puzzle Solved!"); }}
    }}

    bool CheckSolved()
    {{
        int n = 0;
        for (int y = size-1; y >= 0; y--)
        for (int x = 0; x < size; x++)
        {{ if (board[x,y] != n) return false; n++; }}
        return true;
    }}

    bool InBounds(Vector2Int p) => p.x>=0&&p.x<size&&p.y>=0&&p.y<size;
    Vector3 GridToWorld(Vector2Int p) => new Vector3((p.x - (size-1)/2f)*cellSize, (p.y - (size-1)/2f)*cellSize, 0f);
}}
""",

    "lock_puzzle": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Combination lock / cipher puzzle
    [Header("Lock Settings")]
    public int   digits       = 4;
    public int   digitRange   = 10;   // 0-9
    public int[] correctCode;
    public bool  randomizeCode = true;

    private int[] currentCode;
    public event System.Action OnUnlocked;
    public event System.Action OnFailed;

    void Start()
    {{
        currentCode = new int[digits];
        if (randomizeCode || correctCode == null || correctCode.Length != digits)
        {{
            correctCode = new int[digits];
            for (int i = 0; i < digits; i++) correctCode[i] = Random.Range(0, digitRange);
        }}
        Debug.Log($"[DEV] Code: {{string.Join("-", correctCode)}}");
    }}

    public void SetDigit(int position, int value)
    {{
        if (position < 0 || position >= digits) return;
        currentCode[position] = ((value % digitRange) + digitRange) % digitRange;
    }}

    public void IncrementDigit(int position) => SetDigit(position, currentCode[position] + 1);
    public void DecrementDigit(int position) => SetDigit(position, currentCode[position] - 1);

    public bool TryUnlock()
    {{
        for (int i = 0; i < digits; i++)
            if (currentCode[i] != correctCode[i]) {{ OnFailed?.Invoke(); return false; }}
        OnUnlocked?.Invoke();
        Debug.Log("Lock opened!");
        return true;
    }}

    public int GetDigit(int position) => currentCode[position];
    public string GetCurrentCodeString() => string.Join("", currentCode);
}}
""",

    "physics_puzzle": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Physics-based puzzle trigger (Angry Birds / Cut the Rope style)
    [Header("Puzzle Settings")]
    public GameObject[] requiredObjects;  // objects that must hit the trigger
    public bool         requireAll    = true;
    public AudioClip    successSound;
    public GameObject   successEffect;

    private int         hitCount      = 0;
    private AudioSource audioSource;

    public event System.Action OnPuzzleComplete;

    void Start()
    {{
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
    }}

    void OnTriggerEnter2D(Collider2D other)
    {{
        if (IsRequired(other.gameObject))
        {{
            hitCount++;
            int needed = requireAll ? requiredObjects.Length : 1;
            if (hitCount >= needed) Complete();
        }}
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{
        if (IsRequired(col.gameObject))
        {{
            hitCount++;
            int needed = requireAll ? requiredObjects.Length : 1;
            if (hitCount >= needed) Complete();
        }}
    }}

    bool IsRequired(GameObject go)
    {{
        if (requiredObjects == null || requiredObjects.Length == 0) return true;
        foreach (var obj in requiredObjects)
            if (obj == go) return true;
        return false;
    }}

    void Complete()
    {{
        if (successSound  != null) audioSource.PlayOneShot(successSound);
        if (successEffect != null) Instantiate(successEffect, transform.position, Quaternion.identity);
        OnPuzzleComplete?.Invoke();
        Debug.Log("Puzzle complete!");
        gameObject.SetActive(false);
    }}
}}
""",

# ─── TOWER DEFENSE ────────────────────────────────────────────────────────────
    "tower": """using UnityEngine;
using System.Collections;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Tower Stats")]
    public float range        = 5f;
    public float fireRate     = 1f;
    public int   damage       = 20;
    public int   cost         = 50;
    public int   upgradeCost  = 100;
    public int   level        = 1;
    public int   maxLevel     = 3;

    [Header("Visuals")]
    public Transform turret;
    public GameObject bulletPrefab;
    public Transform  firePoint;
    public LineRenderer rangeIndicator;

    private float     nextFireTime;
    private Transform target;

    void Start()   {{ StartCoroutine(FindTarget()); }}
    void Update()  {{ Aim(); Shoot(); }}

    IEnumerator FindTarget()
    {{
        while (true)
        {{
            yield return new WaitForSeconds(0.25f);
            Collider[] cols = Physics.OverlapSphere(transform.position, range, LayerMask.GetMask("Enemy"));
            float closest = float.MaxValue; target = null;
            foreach (var c in cols)
            {{
                float d = Vector3.Distance(transform.position, c.transform.position);
                if (d < closest) {{ closest = d; target = c.transform; }}
            }}
        }}
    }}

    void Aim()
    {{
        if (target == null || turret == null) return;
        Vector3 dir = (target.position - turret.position).normalized;
        dir.y = 0f;
        if (dir != Vector3.zero)
            turret.rotation = Quaternion.Slerp(turret.rotation, Quaternion.LookRotation(dir), 10f * Time.deltaTime);
    }}

    void Shoot()
    {{
        if (target == null || Time.time < nextFireTime || bulletPrefab == null || firePoint == null) return;
        nextFireTime = Time.time + 1f / fireRate;
        GameObject b = Instantiate(bulletPrefab, firePoint.position, firePoint.rotation);
        var tb = b.GetComponent<TowerBullet>();
        if (tb != null) {{ tb.damage = damage; tb.target = target; }}
    }}

    public bool Upgrade()
    {{
        if (level >= maxLevel) return false;
        level++;
        range    *= 1.2f; fireRate *= 1.3f; damage = Mathf.RoundToInt(damage * 1.5f);
        return true;
    }}

    void OnDrawGizmosSelected() {{ Gizmos.color = Color.red; Gizmos.DrawWireSphere(transform.position, range); }}
}}
""",

    "tower_bullet": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    public int       damage    = 20;
    public Transform target;
    public float     speed     = 15f;
    public float     lifetime  = 4f;
    public GameObject hitEffect;

    void Start() {{ Destroy(gameObject, lifetime); }}

    void Update()
    {{
        if (target == null) {{ Destroy(gameObject); return; }}
        float step = speed * Time.deltaTime;
        transform.position = Vector3.MoveTowards(transform.position, target.position, step);
        transform.LookAt(target);
        if (Vector3.Distance(transform.position, target.position) < 0.1f) HitTarget();
    }}

    void HitTarget()
    {{
        if (hitEffect != null) Instantiate(hitEffect, transform.position, Quaternion.identity);
        var hb = target.GetComponent<HealthBar>();
        if (hb != null) hb.TakeDamage(damage);
        else {{ var enemy = target.GetComponent<EnemyAI>(); if(enemy!=null) enemy.TakeDamage(damage); }}
        Destroy(gameObject);
    }}
}}
""",

    "wave_manager": """using UnityEngine;
using System.Collections;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [System.Serializable]
    public class Wave
    {{
        public string  waveName    = "Wave 1";
        public int     enemyCount  = 10;
        public float   spawnRate   = 1f;
        public int     reward      = 50;
        public GameObject[] enemyTypes;
    }}

    [Header("Waves")]
    public Wave[]      waves;
    public Transform[] spawnPoints;
    public float       timeBetweenWaves = 5f;

    private int   currentWave   = 0;
    private int   enemiesAlive  = 0;
    private bool  waveInProgress = false;
    public  int   Gold {{ get; private set; }} = 100;

    public event System.Action<int>  OnWaveStart;
    public event System.Action<int>  OnWaveEnd;
    public event System.Action       OnAllWavesComplete;

    void Start() {{ StartCoroutine(RunWaves()); }}

    IEnumerator RunWaves()
    {{
        for (currentWave = 0; currentWave < waves.Length; currentWave++)
        {{
            yield return new WaitForSeconds(timeBetweenWaves);
            yield return StartCoroutine(SpawnWave(waves[currentWave]));
            while (enemiesAlive > 0) yield return new WaitForSeconds(0.5f);
            Gold += waves[currentWave].reward;
            OnWaveEnd?.Invoke(currentWave);
        }}
        OnAllWavesComplete?.Invoke();
        Debug.Log("All waves complete!");
    }}

    IEnumerator SpawnWave(Wave wave)
    {{
        waveInProgress = true;
        OnWaveStart?.Invoke(currentWave);
        for (int i = 0; i < wave.enemyCount; i++)
        {{
            if (wave.enemyTypes == null || wave.enemyTypes.Length == 0) yield break;
            Transform sp = spawnPoints[Random.Range(0, spawnPoints.Length)];
            GameObject type = wave.enemyTypes[Random.Range(0, wave.enemyTypes.Length)];
            if (type != null)
            {{
                Instantiate(type, sp.position, Quaternion.identity);
                enemiesAlive++;
            }}
            yield return new WaitForSeconds(1f / wave.spawnRate);
        }}
        waveInProgress = false;
    }}

    public void EnemyKilled() {{ enemiesAlive = Mathf.Max(0, enemiesAlive - 1); }}
    public bool SpendGold(int amount) {{ if (Gold < amount) return false; Gold -= amount; return true; }}
    public int CurrentWave => currentWave + 1;
    public int TotalWaves  => waves.Length;
}}
""",

    "path_follower": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Tower defense enemy path follower
    [Header("Path Settings")]
    public float    speed        = 3f;
    public float    waypointThreshold = 0.1f;
    public int      damage       = 10; // damage to base on reaching end
    public bool     destroyAtEnd = true;

    private List<Transform> waypoints;
    private int     waypointIndex = 0;
    public  float   DistanceTravelled {{ get; private set; }}

    public void SetWaypoints(List<Transform> wps) {{ waypoints = wps; }}

    void Update()
    {{
        if (waypoints == null || waypoints.Count == 0) return;
        if (waypointIndex >= waypoints.Count)
        {{
            ReachBase();
            return;
        }}
        Transform target = waypoints[waypointIndex];
        Vector3 dir = (target.position - transform.position).normalized;
        transform.position += dir * speed * Time.deltaTime;
        DistanceTravelled   += speed * Time.deltaTime;
        transform.rotation = Quaternion.LookRotation(dir);
        if (Vector3.Distance(transform.position, target.position) < waypointThreshold)
            waypointIndex++;
    }}

    void ReachBase()
    {{
        // Notify base and deal damage
        var wm = FindObjectOfType<{name.replace("PathFollower","WaveManager") if "PathFollower" in name else "WaveManager"}>();
        Debug.Log($"Enemy reached base! -{damage} lives");
        if (destroyAtEnd) Destroy(gameObject);
    }}
}}
""",

# ─── STRATEGY & RTS ───────────────────────────────────────────────────────────
    "rts_unit": """using UnityEngine;
using UnityEngine.AI;
public class {name} : MonoBehaviour
{{
    [Header("Unit Stats")]
    public string  unitName    = "Soldier";
    public int     maxHealth   = 100;
    public int     damage      = 15;
    public float   attackRange = 2f;
    public float   attackSpeed = 1f;
    public int     team        = 0; // 0 = player, 1 = enemy
    public int     cost        = 50;

    private int          currentHealth;
    private NavMeshAgent agent;
    private {name}       attackTarget;
    private float        nextAttackTime;
    private bool         isSelected;

    public event System.Action<{name}> OnDied;

    void Start()
    {{
        agent = GetComponent<NavMeshAgent>();
        currentHealth = maxHealth;
    }}

    void Update()
    {{
        if (attackTarget != null)
        {{
            float dist = Vector3.Distance(transform.position, attackTarget.transform.position);
            if (dist <= attackRange)
            {{
                agent.ResetPath();
                if (Time.time >= nextAttackTime)
                {{
                    nextAttackTime = Time.time + 1f / attackSpeed;
                    attackTarget.TakeDamage(damage);
                }}
            }}
            else agent.SetDestination(attackTarget.transform.position);
        }}
    }}

    public void MoveTo(Vector3 pos)
    {{
        attackTarget = null;
        if (agent != null) agent.SetDestination(pos);
    }}

    public void Attack({name} target)
    {{
        attackTarget = target;
    }}

    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        OnDied?.Invoke(this);
        Destroy(gameObject);
    }}

    public void Select(bool sel)
    {{
        isSelected = sel;
        // Highlight/unhighlight unit
    }}

    public float HealthPercent => (float)currentHealth / maxHealth;
    public bool  IsSelected    => isSelected;
}}
""",

    "resource_manager": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Generic resource manager — works for RTS, tycoon, city builder, farming
    public static {name} Instance {{ get; private set; }}

    [System.Serializable]
    public class Resource
    {{
        public string name;
        public int    amount;
        public int    maxAmount = 9999;
        public int    incomePerSecond;
    }}

    public List<Resource> resources = new List<Resource>();
    private float incomeTimer;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
        // Default resources
        if (resources.Count == 0)
        {{
            resources.Add(new Resource {{ name="Gold",  amount=500, incomePerSecond=5  }});
            resources.Add(new Resource {{ name="Wood",  amount=200, incomePerSecond=2  }});
            resources.Add(new Resource {{ name="Stone", amount=100, incomePerSecond=1  }});
            resources.Add(new Resource {{ name="Food",  amount=100, incomePerSecond=3  }});
        }}
    }}

    void Update()
    {{
        incomeTimer += Time.deltaTime;
        if (incomeTimer >= 1f)
        {{
            incomeTimer -= 1f;
            foreach (var r in resources)
                r.amount = Mathf.Min(r.amount + r.incomePerSecond, r.maxAmount);
        }}
    }}

    public bool Has(string name, int amount)
    {{
        var r = resources.Find(x => x.name == name);
        return r != null && r.amount >= amount;
    }}

    public bool Spend(string name, int amount)
    {{
        var r = resources.Find(x => x.name == name);
        if (r == null || r.amount < amount) return false;
        r.amount -= amount;
        return true;
    }}

    public void Add(string name, int amount)
    {{
        var r = resources.Find(x => x.name == name);
        if (r != null) r.amount = Mathf.Min(r.amount + amount, r.maxAmount);
    }}

    public int Get(string name)
    {{
        var r = resources.Find(x => x.name == name);
        return r?.amount ?? 0;
    }}
}}
""",

# ─── SPORTS ───────────────────────────────────────────────────────────────────
    "ball_physics": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Generic sports ball — works for football, basketball, tennis, golf
    [Header("Ball Settings")]
    public float     spinFactor     = 0.1f;
    public float     bounciness     = 0.6f;
    public float     airDrag        = 0.02f;
    public float     groundDrag     = 0.8f;
    public float     gravity        = 9.81f;
    public LayerMask groundLayer;

    [Header("Kick/Hit")]
    public float     maxKickForce   = 30f;
    public float     minKickForce   = 5f;
    public AudioClip kickSound;
    public AudioClip bounceSound;

    private Rigidbody   rb;
    private AudioSource audioSource;
    private bool        isGrounded;
    private Vector3     spin;

    public event System.Action<Collision> OnBounce;
    public event System.Action            OnGoal;

    void Awake()
    {{
        rb = GetComponent<Rigidbody>();
        rb.drag        = airDrag;
        rb.angularDrag = 0.5f;
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
    }}

    public void Kick(Vector3 direction, float force)
    {{
        force = Mathf.Clamp(force, minKickForce, maxKickForce);
        rb.velocity = Vector3.zero;
        rb.AddForce(direction.normalized * force, ForceMode.Impulse);
        rb.AddTorque(Vector3.Cross(direction, Vector3.up) * force * spinFactor, ForceMode.Impulse);
        if (kickSound != null) audioSource.PlayOneShot(kickSound);
    }}

    public void Throw(Vector3 releaseVelocity) {{ rb.velocity = releaseVelocity; }}

    void OnCollisionEnter(Collision col)
    {{
        bool isGround = ((1 << col.gameObject.layer) & groundLayer) != 0;
        isGrounded = isGround;
        rb.drag = isGround ? groundDrag : airDrag;
        if (bounceSound != null && rb.velocity.magnitude > 2f)
            audioSource.PlayOneShot(bounceSound, rb.velocity.magnitude / maxKickForce);
        OnBounce?.Invoke(col);
    }}

    void OnTriggerEnter(Collider other)
    {{
        if (other.CompareTag("Goal")) {{ OnGoal?.Invoke(); Debug.Log("GOAL!"); }}
    }}

    public bool IsMoving => rb.velocity.magnitude > 0.1f;
}}
""",

    "scoreboard": """using UnityEngine;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    // Sports scoreboard — teams, scores, timer
    [Header("Team Settings")]
    public string team1Name = "Home";
    public string team2Name = "Away";
    public int    halfCount = 2;
    public float  halfDuration = 300f; // seconds

    [Header("UI")]
    public Text team1NameText, team2NameText;
    public Text team1ScoreText, team2ScoreText;
    public Text timerText, halfText;

    private int   team1Score, team2Score;
    private int   currentHalf = 1;
    private float timeLeft;
    private bool  isRunning;

    public event System.Action<int> OnHalfEnd;
    public event System.Action      OnMatchEnd;

    void Start()
    {{
        timeLeft = halfDuration;
        UpdateUI();
        if (team1NameText) team1NameText.text = team1Name;
        if (team2NameText) team2NameText.text = team2Name;
    }}

    void Update()
    {{
        if (!isRunning) return;
        timeLeft -= Time.deltaTime;
        UpdateTimer();
        if (timeLeft <= 0f) EndHalf();
    }}

    public void StartMatch() {{ isRunning = true; }}
    public void PauseMatch() {{ isRunning = false; }}

    public void ScoreGoal(int team)
    {{
        if (team == 1) {{ team1Score++; if (team1ScoreText) team1ScoreText.text = team1Score.ToString(); }}
        else           {{ team2Score++; if (team2ScoreText) team2ScoreText.text = team2Score.ToString(); }}
    }}

    void EndHalf()
    {{
        isRunning = false;
        OnHalfEnd?.Invoke(currentHalf);
        if (currentHalf >= halfCount) {{ OnMatchEnd?.Invoke(); Debug.Log($"Match over! {{team1Name}} {{team1Score}} - {{team2Score}} {{team2Name}}"); }}
        else {{ currentHalf++; timeLeft = halfDuration; if (halfText) halfText.text = $"Half {{currentHalf}}"; }}
    }}

    void UpdateTimer()
    {{
        if (timerText == null) return;
        int m = Mathf.FloorToInt(timeLeft / 60f);
        int s = Mathf.FloorToInt(timeLeft % 60f);
        timerText.text = $"{{m:00}}:{{s:00}}";
    }}

    void UpdateUI()
    {{
        if (team1ScoreText) team1ScoreText.text = "0";
        if (team2ScoreText) team2ScoreText.text = "0";
        if (halfText)       halfText.text        = $"Half {{currentHalf}}";
    }}
}}
""",

# ─── RHYTHM / MUSIC ───────────────────────────────────────────────────────────
    "rhythm_lane": """using UnityEngine;
using System.Collections;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Rhythm game — Guitar Hero / Piano Tiles style
    [Header("Lanes")]
    public int   laneCount     = 4;
    public float laneWidth     = 1.5f;
    public float noteSpeed     = 8f;
    public float hitY          = -3.5f;  // Y position of hit zone
    public float spawnY        = 5f;

    [Header("Scoring")]
    public float perfectWindow = 0.08f;
    public float goodWindow    = 0.15f;
    public float missWindow    = 0.25f;
    public int   scorePerPerfect = 300;
    public int   scorePerGood    = 100;
    public GameObject notePrefab;
    public AudioClip  hitSound, missSound;
    public KeyCode[]  laneKeys = {{ KeyCode.D, KeyCode.F, KeyCode.J, KeyCode.K }};

    private int            score;
    private int            combo;
    private List<float>[]  noteTimings;
    private AudioSource    audioSource;

    [System.Serializable]
    public class NoteEvent {{ public int lane; public float time; }}
    public List<NoteEvent> beatMap = new List<NoteEvent>();

    void Start()
    {{
        audioSource = GetComponent<AudioSource>();
        noteTimings = new List<float>[laneCount];
        for (int i = 0; i < laneCount; i++) noteTimings[i] = new List<float>();
        StartCoroutine(SpawnNotes());
    }}

    void Update()
    {{
        for (int i = 0; i < Mathf.Min(laneCount, laneKeys.Length); i++)
            if (Input.GetKeyDown(laneKeys[i])) TryHit(i);
    }}

    IEnumerator SpawnNotes()
    {{
        float songTime = 0f;
        foreach (var note in beatMap)
        {{
            float waitTime = note.time - songTime - (spawnY - hitY) / noteSpeed;
            if (waitTime > 0f) {{ yield return new WaitForSeconds(waitTime); songTime = note.time - (spawnY - hitY) / noteSpeed; }}
            SpawnNote(note.lane, note.time);
        }}
    }}

    void SpawnNote(int lane, float hitTime)
    {{
        if (notePrefab == null) return;
        float xPos = (lane - (laneCount-1)/2f) * laneWidth;
        GameObject note = Instantiate(notePrefab, new Vector3(xPos, spawnY, 0f), Quaternion.identity, transform);
        var nr = note.AddComponent<NoteRider>();
        nr.speed = noteSpeed; nr.targetY = hitY; nr.hitTime = hitTime; nr.lane = lane; nr.owner = this;
        noteTimings[lane].Add(hitTime);
    }}

    public void TryHit(int lane)
    {{
        if (noteTimings[lane].Count == 0) {{ Miss(); return; }}
        float songTime = audioSource.isPlaying ? audioSource.time : Time.time;
        float nearest = noteTimings[lane][0];
        float diff = Mathf.Abs(songTime - nearest);
        if (diff <= perfectWindow) {{ Hit(scorePerPerfect, "PERFECT"); noteTimings[lane].RemoveAt(0); }}
        else if (diff <= goodWindow) {{ Hit(scorePerGood, "GOOD");    noteTimings[lane].RemoveAt(0); }}
        else Miss();
    }}

    void Hit(int pts, string rating)
    {{
        combo++; score += pts * combo;
        if (hitSound) audioSource.PlayOneShot(hitSound);
        Debug.Log($"{{rating}}! Combo x{{combo}} Score: {{score}}");
    }}

    void Miss()
    {{
        combo = 0;
        if (missSound) audioSource.PlayOneShot(missSound);
        Debug.Log("Miss!");
    }}

    public int Score => score;
    public int Combo => combo;

    class NoteRider : MonoBehaviour
    {{
        public float speed, targetY, hitTime; public int lane;
        public {name} owner;
        void Update()
        {{
            transform.position += Vector3.down * speed * Time.deltaTime;
            if (transform.position.y < targetY - 1f) {{ owner?.noteTimings[lane]?.Remove(hitTime); Destroy(gameObject); }}
        }}
    }}
}}
""",

# ─── IDLE / CLICKER ───────────────────────────────────────────────────────────
    "idle_manager": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Idle / clicker game manager
    public static {name} Instance {{ get; private set; }}

    [System.Serializable]
    public class Generator
    {{
        public string name;
        public double baseCost;
        public double baseIncome;
        public int    owned;
        public double CostForNext => baseCost * System.Math.Pow(1.15, owned);
        public double TotalIncome => baseIncome * owned;
    }}

    [Header("Currencies")]
    public double currency  = 0;
    public double totalEarned = 0;

    [Header("Generators")]
    public List<Generator> generators = new List<Generator>();

    [Header("Click Settings")]
    public double clickValue = 1;

    private double incomePerSecond;
    private float  incomeTimer;
    private const string SAVE_KEY = "IdleSave";

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else {{ Destroy(gameObject); return; }}
        LoadGame();
        // Default generators
        if (generators.Count == 0)
        {{
            generators.Add(new Generator {{ name="Worker",   baseCost=10,    baseIncome=0.1  }});
            generators.Add(new Generator {{ name="Factory",  baseCost=100,   baseIncome=1    }});
            generators.Add(new Generator {{ name="Mine",     baseCost=500,   baseIncome=6    }});
            generators.Add(new Generator {{ name="Refinery", baseCost=2000,  baseIncome=30   }});
            generators.Add(new Generator {{ name="Portal",   baseCost=10000, baseIncome=200  }});
        }}
    }}

    void Update()
    {{
        incomeTimer += Time.deltaTime;
        if (incomeTimer >= 1f)
        {{
            incomeTimer -= 1f;
            double income = 0;
            foreach (var g in generators) income += g.TotalIncome;
            incomePerSecond = income;
            AddCurrency(income);
        }}
    }}

    public void Click() {{ AddCurrency(clickValue); }}

    public bool BuyGenerator(int index)
    {{
        if (index < 0 || index >= generators.Count) return false;
        double cost = generators[index].CostForNext;
        if (currency < cost) return false;
        currency -= cost;
        generators[index].owned++;
        clickValue = 1 + generators.Count; // auto-upgrade click
        return true;
    }}

    void AddCurrency(double amount) {{ currency += amount; totalEarned += amount; }}

    public void SaveGame()
    {{
        PlayerPrefs.SetString(SAVE_KEY, JsonUtility.ToJson(new SaveWrapper {{ currency=(float)currency, generators=generators }});
    }}

    void LoadGame()
    {{
        string json = PlayerPrefs.GetString(SAVE_KEY, "");
        if (!string.IsNullOrEmpty(json))
        {{
            var w = JsonUtility.FromJson<SaveWrapper>(json);
            if (w != null) {{ currency = w.currency; generators = w.generators; }}
        }}
    }}

    void OnApplicationQuit() {{ SaveGame(); }}
    void OnApplicationPause(bool p) {{ if (p) SaveGame(); }}

    public double IncomePerSecond => incomePerSecond;
    [System.Serializable] class SaveWrapper {{ public float currency; public List<Generator> generators; }}
}}
""",

# ─── STEALTH ──────────────────────────────────────────────────────────────────
    "guard_ai": """using UnityEngine;
using UnityEngine.AI;
public class {name} : MonoBehaviour
{{
    [Header("Guard Settings")]
    public float    patrolSpeed    = 2f;
    public float    chaseSpeed     = 5f;
    public float    sightRange     = 10f;
    public float    sightAngle     = 60f;
    public float    hearRange      = 5f;
    public float    alertTime      = 3f;
    public Transform[] patrolPoints;
    public Light    visionCone;
    public Color    normalColor    = Color.yellow;
    public Color    alertColor     = Color.red;

    private NavMeshAgent agent;
    private Transform    player;
    private int          patrolIndex;
    private float        alertTimer;

    public enum GuardState {{ Patrol, Alert, Chase }}
    private GuardState state = GuardState.Patrol;

    void Start()
    {{
        agent  = GetComponent<NavMeshAgent>();
        agent.speed = patrolSpeed;
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
        if (patrolPoints.Length > 0) agent.SetDestination(patrolPoints[0].position);
        if (visionCone != null) visionCone.color = normalColor;
    }}

    void Update()
    {{
        switch (state)
        {{
            case GuardState.Patrol: Patrol(); break;
            case GuardState.Alert:  Alert();  break;
            case GuardState.Chase:  Chase();  break;
        }}
        UpdateVisionCone();
    }}

    void Patrol()
    {{
        if (patrolPoints.Length == 0) return;
        if (agent.remainingDistance < 0.5f && !agent.pathPending)
        {{
            patrolIndex = (patrolIndex + 1) % patrolPoints.Length;
            agent.SetDestination(patrolPoints[patrolIndex].position);
        }}
        if (CanSeePlayer()) EnterChase();
        else if (CanHearPlayer()) EnterAlert();
    }}

    void Alert()
    {{
        alertTimer -= Time.deltaTime;
        agent.SetDestination(player.position);
        if (CanSeePlayer()) {{ EnterChase(); return; }}
        if (alertTimer <= 0f) {{ state = GuardState.Patrol; agent.speed = patrolSpeed; if (visionCone) visionCone.color = normalColor; }}
    }}

    void Chase()
    {{
        agent.SetDestination(player.position);
        if (!CanSeePlayer()) EnterAlert();
        // TODO: trigger game over or stealth detection event
    }}

    void EnterAlert() {{ state = GuardState.Alert; alertTimer = alertTime; agent.speed = chaseSpeed * 0.7f; if (visionCone) visionCone.color = Color.Lerp(normalColor, alertColor, 0.5f); }}
    void EnterChase() {{ state = GuardState.Chase; agent.speed = chaseSpeed; if (visionCone) visionCone.color = alertColor; Debug.Log("Guard spotted player!"); }}

    bool CanSeePlayer()
    {{
        if (player == null) return false;
        float dist  = Vector3.Distance(transform.position, player.position);
        if (dist > sightRange) return false;
        Vector3 dir = (player.position - transform.position).normalized;
        if (Vector3.Angle(transform.forward, dir) > sightAngle/2f) return false;
        return !Physics.Raycast(transform.position + Vector3.up, dir, dist, LayerMask.GetMask("Wall","Obstacle"));
    }}

    bool CanHearPlayer() => player != null && Vector3.Distance(transform.position, player.position) < hearRange;

    void UpdateVisionCone()
    {{
        if (visionCone == null) return;
        visionCone.range       = sightRange;
        visionCone.spotAngle   = sightAngle;
    }}
}}
""",

    "stealth_player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Stealth Settings")]
    public float  walkSpeed     = 3f;
    public float  crouchSpeed   = 1.5f;
    public float  runSpeed      = 6f;
    public float  noiseRadius   = 3f;
    public float  crouchNoise   = 0.5f;
    public float  runNoise      = 8f;

    [Header("Status")]
    public float  visibility    = 0f;  // 0=invisible, 1=fully seen
    public bool   isDetected    = false;

    private bool  isCrouching   = false;
    private bool  isRunning     = false;
    private float currentNoise;
    private Rigidbody rb;
    private CapsuleCollider col;

    public event System.Action OnDetected;
    public event System.Action OnEscaped;

    void Start()
    {{
        rb  = GetComponent<Rigidbody>();
        col = GetComponent<CapsuleCollider>();
    }}

    void Update()
    {{
        isCrouching = Input.GetKey(KeyCode.C) || Input.GetKey(KeyCode.LeftControl);
        isRunning   = Input.GetKey(KeyCode.LeftShift) && !isCrouching;

        float spd = isCrouching ? crouchSpeed : isRunning ? runSpeed : walkSpeed;
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        rb.velocity = new Vector3(h * spd, rb.velocity.y, v * spd);

        // Noise emission
        float moveMag = new Vector3(h,0f,v).magnitude;
        currentNoise  = moveMag > 0.1f
            ? (isCrouching ? crouchNoise : isRunning ? runNoise : noiseRadius)
            : 0f;

        // Crouch height
        if (col != null) col.height = isCrouching ? 1f : 1.8f;
    }}

    public void SetDetected(bool detected)
    {{
        if (detected && !isDetected) {{ isDetected = true; OnDetected?.Invoke(); }}
        else if (!detected && isDetected) {{ isDetected = false; OnEscaped?.Invoke(); }}
    }}

    public float NoiseRadius => currentNoise;
    public bool  IsCrouching => isCrouching;
    public bool  IsRunning   => isRunning;
}}
""",

# ─── RACING (Extended) ────────────────────────────────────────────────────────
    "lap_manager": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Race Settings")]
    public int   totalLaps       = 3;
    public float countdownTime   = 3f;
    public Transform[] checkpoints;

    private Dictionary<GameObject,int> lapCounts   = new Dictionary<GameObject,int>();
    private Dictionary<GameObject,int> cpProgress  = new Dictionary<GameObject,int>();
    private Dictionary<GameObject,float> bestLapTimes = new Dictionary<GameObject,float>();
    private Dictionary<GameObject,float> lapStartTimes = new Dictionary<GameObject,float>();
    private bool raceStarted, raceFinished;
    private float countdown;

    public event System.Action<GameObject,int> OnLapComplete;
    public event System.Action<GameObject>     OnRaceFinished;

    void Start()
    {{
        countdown = countdownTime;
        Debug.Log($"Race in {{countdownTime:F0}}...");
    }}

    void Update()
    {{
        if (!raceStarted)
        {{
            countdown -= Time.deltaTime;
            if (countdown <= 0f) {{ raceStarted = true; Debug.Log("GO!"); }}
            return;
        }}
    }}

    public void RegisterRacer(GameObject racer)
    {{
        lapCounts[racer]    = 0;
        cpProgress[racer]   = 0;
        lapStartTimes[racer] = Time.time;
    }}

    public void OnCheckpointHit(GameObject racer, int cpIndex)
    {{
        if (!raceStarted || raceFinished) return;
        if (!lapCounts.ContainsKey(racer)) RegisterRacer(racer);
        if (cpIndex == cpProgress[racer])
        {{
            cpProgress[racer]++;
            if (cpProgress[racer] >= checkpoints.Length)
            {{
                // Completed a lap
                cpProgress[racer] = 0;
                lapCounts[racer]++;
                float lapTime = Time.time - lapStartTimes[racer];
                if (!bestLapTimes.ContainsKey(racer) || lapTime < bestLapTimes[racer])
                    bestLapTimes[racer] = lapTime;
                lapStartTimes[racer] = Time.time;
                OnLapComplete?.Invoke(racer, lapCounts[racer]);
                Debug.Log($"{{racer.name}} completed lap {{lapCounts[racer]}}/{{totalLaps}} in {{lapTime:F2}}s");
                if (lapCounts[racer] >= totalLaps)
                {{
                    raceFinished = true;
                    OnRaceFinished?.Invoke(racer);
                    Debug.Log($"{{racer.name}} WINS!");
                }}
            }}
        }}
    }}

    public int  GetLap(GameObject r)     => lapCounts.ContainsKey(r)  ? lapCounts[r]  : 0;
    public bool RaceStarted              => raceStarted;
    public bool RaceFinished             => raceFinished;
}}
""",

# ─── PLATFORMER SYSTEMS ───────────────────────────────────────────────────────
    "platformer_player": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Movement")]
    public float moveSpeed     = 6f;
    public float jumpForce     = 12f;
    public float doubleJumpForce = 10f;
    public float wallJumpForce = 8f;
    public float coyoteTime    = 0.12f;
    public float jumpBuffer    = 0.1f;

    [Header("Ground Check")]
    public Transform groundCheck;
    public float     groundRadius = 0.2f;
    public LayerMask groundLayer;

    private Rigidbody2D  rb;
    private Animator     anim;
    private bool         isGrounded, canDoubleJump, isWallSliding;
    private float        coyoteTimer, jumpBufferTimer;
    private float        wallDir;

    void Start()
    {{
        rb   = GetComponent<Rigidbody2D>();
        anim = GetComponent<Animator>();
    }}

    void Update()
    {{
        // Ground check
        isGrounded = Physics2D.OverlapCircle(groundCheck ? groundCheck.position : transform.position + Vector3.down*0.5f, groundRadius, groundLayer);
        if (isGrounded) {{ coyoteTimer = coyoteTime; canDoubleJump = true; }}
        else coyoteTimer -= Time.deltaTime;

        // Jump buffer
        if (Input.GetButtonDown("Jump")) jumpBufferTimer = jumpBuffer;
        else jumpBufferTimer -= Time.deltaTime;

        // Jump
        if (jumpBufferTimer > 0f)
        {{
            if (coyoteTimer > 0f)           {{ Jump(jumpForce);       jumpBufferTimer = 0f; coyoteTimer = 0f; }}
            else if (canDoubleJump)          {{ Jump(doubleJumpForce); jumpBufferTimer = 0f; canDoubleJump = false; }}
        }}

        // Horizontal movement
        float h = Input.GetAxis("Horizontal");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y);
        if (h != 0f) transform.localScale = new Vector3(Mathf.Sign(h), 1f, 1f);

        // Animations
        if (anim != null)
        {{
            anim.SetBool("isGrounded", isGrounded);
            anim.SetFloat("speed", Mathf.Abs(h));
            anim.SetFloat("yVelocity", rb.velocity.y);
        }}
    }}

    void Jump(float force)
    {{
        rb.velocity = new Vector2(rb.velocity.x, 0f);
        rb.AddForce(Vector2.up * force, ForceMode2D.Impulse);
    }}

    void OnCollisionEnter2D(Collision2D col)
    {{ if (col.gameObject.CompareTag("Ground") || ((1<<col.gameObject.layer)&groundLayer)!=0) isGrounded = true; }}

    public bool IsGrounded => isGrounded;
}}
""",

    "checkpoint_system": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Universal checkpoint / respawn system
    public static {name} Instance {{ get; private set; }}

    [Header("Respawn Settings")]
    public float  respawnDelay  = 2f;
    public int    maxLives      = 3;
    public bool   infiniteLives = false;

    private Vector3    respawnPoint;
    private Quaternion respawnRotation;
    private int        currentLives;
    private float      respawnTimer;
    private bool       isDead;
    private GameObject player;

    public event System.Action<int> OnLifeLost;
    public event System.Action      OnGameOver;
    public event System.Action      OnRespawn;

    void Awake()
    {{
        if (Instance == null) Instance = this; else Destroy(gameObject);
        currentLives = maxLives;
        player = GameObject.FindGameObjectWithTag("Player");
        if (player != null) {{ respawnPoint = player.transform.position; respawnRotation = player.transform.rotation; }}
    }}

    void Update()
    {{
        if (isDead)
        {{
            respawnTimer -= Time.deltaTime;
            if (respawnTimer <= 0f) DoRespawn();
        }}
    }}

    public void SetCheckpoint(Vector3 pos, Quaternion rot)
    {{
        respawnPoint    = pos;
        respawnRotation = rot;
        Debug.Log($"Checkpoint saved at {{pos}}");
    }}

    public void PlayerDied()
    {{
        if (isDead) return;
        isDead = true;
        respawnTimer = respawnDelay;
        if (!infiniteLives)
        {{
            currentLives--;
            OnLifeLost?.Invoke(currentLives);
            if (currentLives <= 0) {{ OnGameOver?.Invoke(); return; }}
        }}
        if (player != null) player.SetActive(false);
    }}

    void DoRespawn()
    {{
        isDead = false;
        if (player != null)
        {{
            player.transform.SetPositionAndRotation(respawnPoint, respawnRotation);
            player.SetActive(true);
            // Reset velocity
            var rb = player.GetComponent<Rigidbody2D>();
            if (rb) rb.velocity = Vector2.zero;
            var rb3 = player.GetComponent<Rigidbody>();
            if (rb3) rb3.velocity = Vector3.zero;
        }}
        OnRespawn?.Invoke();
    }}

    public int Lives => currentLives;
}}
""",

# ─── TYCOON / CITY BUILDER ────────────────────────────────────────────────────
    "building": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Building Data")]
    public string buildingName = "Building";
    public int    buildCost    = 100;
    public int    incomePerSecond = 5;
    public int    maintenanceCost = 1;
    public int    capacity     = 10;
    public int    level        = 1;
    public int    maxLevel     = 5;
    public int    upgradeCost  = 200;

    [Header("State")]
    public bool   isBuilt      = false;
    public bool   isPaused     = false;
    public int    currentOccupancy = 0;

    private float incomeTimer;

    public event System.Action<int> OnIncomeGenerated;
    public event System.Action      OnUpgraded;

    void Update()
    {{
        if (!isBuilt || isPaused) return;
        incomeTimer += Time.deltaTime;
        if (incomeTimer >= 1f)
        {{
            incomeTimer -= 1f;
            int income = Mathf.RoundToInt(incomePerSecond * level * ((float)currentOccupancy / Mathf.Max(1, capacity)));
            if (income > 0) OnIncomeGenerated?.Invoke(income);
        }}
    }}

    public bool Build()
    {{
        if (isBuilt) return false;
        var rm = ResourceManager.Instance;
        if (rm != null && !rm.Spend("Gold", buildCost)) return false;
        isBuilt = true;
        Debug.Log($"{{buildingName}} built!");
        return true;
    }}

    public bool Upgrade()
    {{
        if (!isBuilt || level >= maxLevel) return false;
        var rm = ResourceManager.Instance;
        if (rm != null && !rm.Spend("Gold", upgradeCost * level)) return false;
        level++;
        incomePerSecond = Mathf.RoundToInt(incomePerSecond * 1.5f);
        capacity        = Mathf.RoundToInt(capacity        * 1.3f);
        upgradeCost     = Mathf.RoundToInt(upgradeCost     * 1.8f);
        OnUpgraded?.Invoke();
        return true;
    }}

    public void AddOccupant()  {{ currentOccupancy = Mathf.Min(currentOccupancy + 1, capacity); }}
    public void RemoveOccupant(){{ currentOccupancy = Mathf.Max(0, currentOccupancy - 1); }}
    public float OccupancyRate  => capacity > 0 ? (float)currentOccupancy / capacity : 0f;
}}
""",

# ─── FARMING / SURVIVAL ───────────────────────────────────────────────────────
    "farmable": """using UnityEngine;
using System.Collections;
public class {name} : MonoBehaviour
{{
    // Plant/crop/tree — works for farming, survival games
    [Header("Crop Settings")]
    public string  cropName      = "Wheat";
    public float   growthTime    = 30f; // seconds
    public int     yield         = 3;
    public int     seedCost      = 5;
    public Sprite[] growthStages;  // 0=seed, last=ready
    public AudioClip plantSound, harvestSound;

    private float       growthProgress = 0f;
    private bool        isReady        = false;
    private bool        isPlanted      = false;
    private int         currentStage   = 0;
    private SpriteRenderer sr;
    private AudioSource audio;

    void Awake()
    {{
        sr    = GetComponent<SpriteRenderer>();
        audio = GetComponent<AudioSource>();
        if (audio == null) audio = gameObject.AddComponent<AudioSource>();
    }}

    public void Plant()
    {{
        isPlanted = true; isReady = false; growthProgress = 0f; currentStage = 0;
        UpdateSprite();
        if (plantSound) audio.PlayOneShot(plantSound);
        StartCoroutine(Grow());
    }}

    IEnumerator Grow()
    {{
        while (growthProgress < 1f)
        {{
            yield return new WaitForSeconds(growthTime / 100f);
            growthProgress += 0.01f;
            int stage = Mathf.FloorToInt(growthProgress * (growthStages.Length - 1));
            if (stage != currentStage) {{ currentStage = stage; UpdateSprite(); }}
        }}
        isReady = true;
        currentStage = growthStages.Length - 1;
        UpdateSprite();
    }}

    public int Harvest()
    {{
        if (!isReady) return 0;
        if (harvestSound) audio.PlayOneShot(harvestSound);
        isPlanted = false; isReady = false; growthProgress = 0f; currentStage = 0;
        UpdateSprite();
        return yield;
    }}

    void UpdateSprite()
    {{
        if (sr != null && growthStages != null && growthStages.Length > 0)
            sr.sprite = growthStages[Mathf.Clamp(currentStage, 0, growthStages.Length-1)];
    }}

    public bool IsReady   => isReady;
    public bool IsPlanted => isPlanted;
    public float GrowthPercent => growthProgress;
}}
""",

    "hunger_thirst": """using UnityEngine;
public class {name} : MonoBehaviour
{{
    // Survival needs — hunger, thirst, temperature
    [Header("Needs")]
    public float maxHunger      = 100f;
    public float maxThirst      = 100f;
    public float maxStamina     = 100f;
    public float hungerDrainRate = 1f;   // per second
    public float thirstDrainRate = 1.5f;
    public float staminaDrainRate = 10f; // while running
    public float staminaRegenRate = 5f;
    public float damageBelowZero  = 2f;  // health damage per second when starving

    private float hunger, thirst, stamina;
    private HealthBar healthBar;
    private bool isRunning;

    public event System.Action OnStarving;
    public event System.Action OnDehydrated;

    void Start()
    {{
        hunger = maxHunger; thirst = maxThirst; stamina = maxStamina;
        healthBar = GetComponent<HealthBar>();
    }}

    void Update()
    {{
        isRunning = Input.GetKey(KeyCode.LeftShift);

        hunger  = Mathf.Max(0f, hunger  - hungerDrainRate  * Time.deltaTime);
        thirst  = Mathf.Max(0f, thirst  - thirstDrainRate  * Time.deltaTime);
        stamina = isRunning
            ? Mathf.Max(0f, stamina - staminaDrainRate * Time.deltaTime)
            : Mathf.Min(maxStamina, stamina + staminaRegenRate * Time.deltaTime);

        if (hunger <= 0f) {{ OnStarving?.Invoke();     if (healthBar) healthBar.TakeDamage(Mathf.RoundToInt(damageBelowZero * Time.deltaTime)); }}
        if (thirst <= 0f) {{ OnDehydrated?.Invoke();   if (healthBar) healthBar.TakeDamage(Mathf.RoundToInt(damageBelowZero * 1.5f * Time.deltaTime)); }}
    }}

    public void Eat(float amount)   {{ hunger  = Mathf.Min(maxHunger,  hunger  + amount); }}
    public void Drink(float amount) {{ thirst  = Mathf.Min(maxThirst,  thirst  + amount); }}
    public void Rest(float amount)  {{ stamina = Mathf.Min(maxStamina, stamina + amount); }}

    public float HungerPercent  => hunger  / maxHunger;
    public float ThirstPercent  => thirst  / maxThirst;
    public float StaminaPercent => stamina / maxStamina;
    public bool  CanRun         => stamina > 10f;
}}
""",

# ─── MULTIPLAYER READY ────────────────────────────────────────────────────────
    "network_player": """using UnityEngine;
// Multiplayer-ready player — works with Mirror, Photon, Unity Netcode
// Stub: replace [Network attributes] with your framework's equivalents
public class {name} : MonoBehaviour
{{
    [Header("Multiplayer")]
    public bool  isLocalPlayer = true;  // set by network framework
    public int   playerID      = 0;
    public string playerName   = "Player";
    public Color playerColor   = Color.white;

    [Header("Movement")]
    public float moveSpeed = 5f;

    [Header("Combat")]
    public int maxHealth = 100;
    private int currentHealth;
    private Rigidbody rb;

    public event System.Action<int,int> OnHealthChanged; // current, max
    public event System.Action          OnDied;

    void Start()
    {{
        rb = GetComponent<Rigidbody>();
        currentHealth = maxHealth;
        // Set player color/name if Renderer exists
        var rend = GetComponentInChildren<Renderer>();
        if (rend != null) rend.material.color = playerColor;
    }}

    void Update()
    {{
        if (!isLocalPlayer) return; // Only control local player
        HandleInput();
    }}

    void HandleInput()
    {{
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        if (rb != null) rb.velocity = new Vector3(h * moveSpeed, rb.velocity.y, v * moveSpeed);
        if (Input.GetButtonDown("Fire1")) CmdShoot();
    }}

    // Network command placeholder — replace with your framework's [Command] attribute
    void CmdShoot()
    {{
        // In Mirror: [Command] void CmdShoot() → calls RpcShoot on all clients
        // In Photon: photonView.RPC("RpcShoot", RpcTarget.All)
        Debug.Log($"{{playerName}} shoots!");
    }}

    public void TakeDamage(int dmg, int attackerID)
    {{
        if (!isLocalPlayer) return; // Only process on owner
        currentHealth = Mathf.Max(0, currentHealth - dmg);
        OnHealthChanged?.Invoke(currentHealth, maxHealth);
        if (currentHealth <= 0) Die();
    }}

    void Die()
    {{
        OnDied?.Invoke();
        Debug.Log($"{{playerName}} died!");
        // In network game: disable and request respawn from server
        gameObject.SetActive(false);
    }}

    public float HealthPercent => (float)currentHealth / maxHealth;
}}
""",

# ─── BULLET HELL ──────────────────────────────────────────────────────────────
    "bullet_pattern": """using UnityEngine;
using System.Collections;
public class {name} : MonoBehaviour
{{
    // Bullet hell / danmaku pattern emitter
    [Header("Pattern Settings")]
    public GameObject bulletPrefab;
    public int        bulletsPerBurst  = 16;
    public float      burstFireRate    = 0.5f;
    public float      bulletSpeed      = 6f;
    public bool       spiral           = false;
    public float      spiralSpeed      = 45f;
    public int        layerCount       = 3;
    public float      layerDelay       = 0.1f;
    public bool       aimedAtPlayer    = false;

    private float     spiralAngle      = 0f;
    private Transform player;
    private bool      isShooting       = true;

    void Start()
    {{
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
        StartCoroutine(ShootLoop());
    }}

    IEnumerator ShootLoop()
    {{
        while (isShooting)
        {{
            yield return new WaitForSeconds(burstFireRate);
            for (int layer = 0; layer < layerCount; layer++)
            {{
                FireBurst(spiralAngle + layer * (360f / layerCount));
                yield return new WaitForSeconds(layerDelay);
            }}
            if (spiral) spiralAngle += spiralSpeed * burstFireRate;
        }}
    }}

    void FireBurst(float baseAngle)
    {{
        if (bulletPrefab == null) return;
        float aimOffset = 0f;
        if (aimedAtPlayer && player != null)
        {{
            Vector2 dir = player.position - transform.position;
            aimOffset = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f;
        }}
        for (int i = 0; i < bulletsPerBurst; i++)
        {{
            float angle = baseAngle + aimOffset + i * (360f / bulletsPerBurst);
            Vector2 dir = new Vector2(Mathf.Sin(angle * Mathf.Deg2Rad), Mathf.Cos(angle * Mathf.Deg2Rad));
            GameObject b = Instantiate(bulletPrefab, transform.position, Quaternion.identity);
            Rigidbody2D brb = b.GetComponent<Rigidbody2D>();
            if (brb != null) brb.velocity = dir * bulletSpeed;
            Destroy(b, 6f);
        }}
    }}

    public void StopShooting() {{ isShooting = false; StopAllCoroutines(); }}
    public void StartShooting() {{ isShooting = true;  StartCoroutine(ShootLoop()); }}
}}
""",

# ─── GACHA / LOOT BOX ─────────────────────────────────────────────────────────
    "gacha_system": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Gacha / loot box / randomized reward system
    public static {name} Instance {{ get; private set; }}

    [System.Serializable]
    public class GachaItem
    {{
        public string name;
        public Sprite icon;
        public float  weight;      // higher = more common
        public enum Rarity {{ Common, Rare, Epic, Legendary }}
        public Rarity rarity = Rarity.Common;
    }}

    [Header("Pool")]
    public List<GachaItem> itemPool = new List<GachaItem>();
    public int    pullCost          = 100;
    public int    guaranteedPity    = 90; // pity system

    private int   pullCount         = 0;
    private int   currency          = 0;
    private List<GachaItem> obtained = new List<GachaItem>();

    public event System.Action<GachaItem>       OnPullResult;
    public event System.Action<List<GachaItem>> OnMultiPull;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else Destroy(gameObject);
    }}

    public GachaItem Pull()
    {{
        if (currency < pullCost) {{ Debug.Log("Not enough currency!"); return null; }}
        currency -= pullCost;
        pullCount++;

        GachaItem result;
        if (pullCount >= guaranteedPity)
        {{
            // Pity: guaranteed rare or above
            var highRarity = itemPool.FindAll(i => i.rarity >= GachaItem.Rarity.Rare);
            result = highRarity.Count > 0 ? WeightedRandom(highRarity) : WeightedRandom(itemPool);
            pullCount = 0;
        }}
        else result = WeightedRandom(itemPool);

        obtained.Add(result);
        OnPullResult?.Invoke(result);
        Debug.Log($"Got: [{result.rarity}] {{result.name}}");
        return result;
    }}

    public List<GachaItem> MultiPull(int count)
    {{
        var results = new List<GachaItem>();
        for (int i = 0; i < count; i++) {{ var r = Pull(); if (r != null) results.Add(r); }}
        OnMultiPull?.Invoke(results);
        return results;
    }}

    GachaItem WeightedRandom(List<GachaItem> pool)
    {{
        float total = 0f;
        foreach (var item in pool) total += item.weight;
        float roll = Random.Range(0f, total);
        float cumulative = 0f;
        foreach (var item in pool)
        {{
            cumulative += item.weight;
            if (roll <= cumulative) return item;
        }}
        return pool[pool.Count - 1];
    }}

    public void AddCurrency(int amount) {{ currency += amount; }}
    public int  Currency  => currency;
    public int  PullCount => pullCount;
    public List<GachaItem> Obtained => new List<GachaItem>(obtained);
}}
""",

# ─── ESCAPE ROOM ──────────────────────────────────────────────────────────────
    "puzzle_trigger": """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    // Escape room puzzle chain trigger
    [Header("Puzzle Chain")]
    public List<GameObject> puzzleSteps;
    public int currentStep = 0;

    [Header("Rewards")]
    public GameObject[] unlockObjects;  // doors, items to reveal when complete
    public AudioClip    solveSound;
    public AudioClip    failSound;
    public string       completionMessage = "Puzzle Solved!";

    private AudioSource audioSource;
    private bool        isComplete = false;

    public event System.Action OnPuzzleChainComplete;

    void Start()
    {{
        audioSource = GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();
        RefreshSteps();
    }}

    void RefreshSteps()
    {{
        for (int i = 0; i < puzzleSteps.Count; i++)
            if (puzzleSteps[i] != null) puzzleSteps[i].SetActive(i == currentStep);
    }}

    public void StepSolved()
    {{
        if (isComplete) return;
        if (solveSound) audioSource.PlayOneShot(solveSound);
        currentStep++;
        if (currentStep >= puzzleSteps.Count)
        {{
            CompletePuzzle();
        }}
        else
        {{
            RefreshSteps();
            Debug.Log($"Step {{currentStep}}/{{puzzleSteps.Count}} — next puzzle");
        }}
    }}

    public void StepFailed()
    {{
        if (failSound) audioSource.PlayOneShot(failSound);
        Debug.Log("Wrong!");
    }}

    void CompletePuzzle()
    {{
        isComplete = true;
        Debug.Log(completionMessage);
        foreach (var obj in unlockObjects)
            if (obj != null) obj.SetActive(true);
        OnPuzzleChainComplete?.Invoke();
    }}

    public bool IsComplete => isComplete;
    public float Progress  => puzzleSteps.Count > 0 ? (float)currentStep / puzzleSteps.Count : 1f;
}}
""",

})


# Roles that use UNIVERSAL_TEMPLATES (full, compilable — NO LLM generation)
# ── Extra game type templates ─────────────────────────────────

UNIVERSAL_TEMPLATES["fishing"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Fishing")]
    public float castDistance = 10f;
    public float biteTime = 3f;
    public float reelSpeed = 2f;
    public GameObject bobberPrefab;
    private GameObject bobber;
    private bool isCasting = false;
    private bool hasBite = false;
    private float biteTimer = 0f;
    void Update()
    {{
        if (Input.GetButtonDown("Fire1") && !isCasting) Cast();
        if (isCasting && hasBite && Input.GetButtonDown("Fire1")) Reel();
        if (isCasting && !hasBite) {{ biteTimer -= Time.deltaTime; if (biteTimer <= 0) {{ hasBite = true; print("Fish on the line!"); }} }}
    }}
    void Cast()
    {{
        Vector3 target = transform.position + transform.forward * castDistance;
        if (bobberPrefab != null) bobber = Instantiate(bobberPrefab, target, Quaternion.identity);
        isCasting = true; hasBite = false; biteTimer = biteTime;
    }}
    void Reel()
    {{
        isCasting = false; hasBite = false;
        if (bobber != null) Destroy(bobber);
        GameManager gm = FindObjectOfType<GameManager>();
        if (gm != null) gm.OnFishCaught();
    }}
}}"""

UNIVERSAL_TEMPLATES["cooking"] = """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Cooking")]
    public List<string> recipe = new List<string>();
    public List<string> addedIngredients = new List<string>();
    public float cookTime = 5f;
    private bool isCooking = false;
    private float cookTimer = 0f;
    void Update()
    {{
        if (isCooking) {{ cookTimer -= Time.deltaTime; if (cookTimer <= 0) FinishCooking(); }}
    }}
    public void AddIngredient(string ingredient)
    {{
        addedIngredients.Add(ingredient);
        CheckRecipe();
    }}
    void CheckRecipe()
    {{
        foreach (string r in recipe)
            if (!addedIngredients.Contains(r)) return;
        isCooking = true; cookTimer = cookTime;
    }}
    void FinishCooking()
    {{
        isCooking = false; addedIngredients.Clear();
        print("Dish complete!");
        GameManager gm = FindObjectOfType<GameManager>(); if (gm != null) gm.OnDishComplete();
    }}
}}"""

UNIVERSAL_TEMPLATES["crafting"] = """using UnityEngine;
using System.Collections.Generic;
[System.Serializable]
public class CraftRecipe {{ public string result; public List<string> ingredients; }}
public class {name} : MonoBehaviour
{{
    public List<CraftRecipe> recipes = new List<CraftRecipe>();
    public List<string> playerInventory = new List<string>();
    public string TryCraft(List<string> selectedItems)
    {{
        foreach (CraftRecipe recipe in recipes)
        {{
            bool match = true;
            foreach (string ing in recipe.ingredients)
                if (!selectedItems.Contains(ing)) {{ match = false; break; }}
            if (match)
            {{
                foreach (string ing in recipe.ingredients) playerInventory.Remove(ing);
                playerInventory.Add(recipe.result);
                return recipe.result;
            }}
        }}
        return null;
    }}
    public void AddItem(string item) {{ playerInventory.Add(item); }}
    public bool HasItem(string item) {{ return playerInventory.Contains(item); }}
}}"""

UNIVERSAL_TEMPLATES["combo_system"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Combo")]
    public float comboWindow = 0.8f;
    public int maxCombo = 5;
    public int damage = 10;
    private int comboCount = 0;
    private float comboTimer = 0f;
    void Update()
    {{
        if (comboTimer > 0) comboTimer -= Time.deltaTime;
        else comboCount = 0;
        if (Input.GetButtonDown("Fire1")) Attack();
    }}
    void Attack()
    {{
        comboCount = Mathf.Min(comboCount + 1, maxCombo);
        comboTimer = comboWindow;
        int totalDamage = damage * comboCount;
        print($"Combo x{{comboCount}} — Damage: {{totalDamage}}");
        Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, 1.5f);
        foreach (var hit in hits)
            if (hit.CompareTag("Enemy"))
            {{
                EnemyScript e = hit.GetComponent<EnemyScript>();
                if (e != null) e.TakeDamage(totalDamage);
            }}
    }}
}}"""

UNIVERSAL_TEMPLATES["zone_shrink"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Safe Zone")]
    public float startRadius = 100f;
    public float endRadius = 5f;
    public float shrinkDuration = 300f;
    public float damagePerSecond = 5f;
    public Transform zoneCenter;
    private float currentRadius;
    private float elapsed = 0f;
    void Start() {{ currentRadius = startRadius; }}
    void Update()
    {{
        elapsed += Time.deltaTime;
        float t = Mathf.Clamp01(elapsed / shrinkDuration);
        currentRadius = Mathf.Lerp(startRadius, endRadius, t);
        transform.localScale = Vector3.one * currentRadius * 2f;
        DamagePlayersOutside();
    }}
    void DamagePlayersOutside()
    {{
        GameObject[] players = GameObject.FindGameObjectsWithTag("Player");
        foreach (GameObject p in players)
        {{
            float dist = Vector3.Distance(p.transform.position, zoneCenter != null ? zoneCenter.position : Vector3.zero);
            if (dist > currentRadius)
            {{
                HealthBar hb = p.GetComponent<HealthBar>();
                if (hb != null) hb.TakeDamage(Mathf.RoundToInt(damagePerSecond * Time.deltaTime));
            }}
        }}
    }}
    public float GetRadius() {{ return currentRadius; }}
}}"""

UNIVERSAL_TEMPLATES["roguelike_room"] = """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Room")]
    public List<GameObject> enemyPrefabs = new List<GameObject>();
    public List<Transform> spawnPoints = new List<Transform>();
    public List<GameObject> doors = new List<GameObject>();
    public GameObject rewardPrefab;
    private int enemiesAlive = 0;
    private bool cleared = false;
    void Start() {{ SpawnEnemies(); }}
    void SpawnEnemies()
    {{
        if (enemyPrefabs.Count == 0 || spawnPoints.Count == 0) {{ ClearRoom(); return; }}
        CloseDoors();
        foreach (Transform sp in spawnPoints)
        {{
            GameObject prefab = enemyPrefabs[Random.Range(0, enemyPrefabs.Count)];
            Instantiate(prefab, sp.position, Quaternion.identity);
            enemiesAlive++;
        }}
    }}
    public void OnEnemyKilled()
    {{
        enemiesAlive = Mathf.Max(0, enemiesAlive - 1);
        if (enemiesAlive == 0) ClearRoom();
    }}
    void ClearRoom()
    {{
        if (cleared) return; cleared = true;
        OpenDoors();
        if (rewardPrefab != null) Instantiate(rewardPrefab, transform.position, Quaternion.identity);
    }}
    void CloseDoors() {{ foreach (GameObject d in doors) if (d != null) d.SetActive(true); }}
    void OpenDoors()  {{ foreach (GameObject d in doors) if (d != null) d.SetActive(false); }}
}}"""

UNIVERSAL_TEMPLATES["moba_hero"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Hero Stats")]
    public float moveSpeed = 5f;
    public int maxHealth = 500;
    public int attackDamage = 50;
    public float attackRange = 2f;
    public float attackCooldown = 1f;
    public float abilityRange = 5f;
    private int currentHealth;
    private float attackTimer = 0f;
    private Rigidbody rb;
    void Start() {{ rb = GetComponent<Rigidbody>(); currentHealth = maxHealth; }}
    void Update()
    {{
        float h = Input.GetAxis("Horizontal"), v = Input.GetAxis("Vertical");
        rb.velocity = new Vector3(h, 0, v) * moveSpeed;
        attackTimer -= Time.deltaTime;
        if (Input.GetButtonDown("Fire1") && attackTimer <= 0) BasicAttack();
        if (Input.GetKeyDown(KeyCode.Q)) UseAbility();
    }}
    void BasicAttack()
    {{
        attackTimer = attackCooldown;
        Collider[] hits = Physics.OverlapSphere(transform.position, attackRange);
        foreach (var hit in hits)
            if (hit.CompareTag("Enemy")) {{ hit.GetComponent<HealthBar>()?.TakeDamage(attackDamage); break; }}
    }}
    void UseAbility()
    {{
        Collider[] hits = Physics.OverlapSphere(transform.position, abilityRange);
        foreach (var hit in hits)
            if (hit.CompareTag("Enemy")) hit.GetComponent<HealthBar>()?.TakeDamage(attackDamage * 2);
    }}
    public void TakeDamage(int dmg)
    {{
        currentHealth -= dmg;
        if (currentHealth <= 0) Die();
    }}
    void Die() {{ Destroy(gameObject); }}
}}"""

UNIVERSAL_TEMPLATES["lane_switcher"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Lanes")]
    public float[] lanePositions = {{ -2f, 0f, 2f }};
    public float laneSpeed = 10f;
    public float runSpeed = 8f;
    private int currentLane = 1;
    private float targetX;
    private Rigidbody rb;
    void Start() {{ rb = GetComponent<Rigidbody>(); targetX = lanePositions[currentLane]; }}
    void Update()
    {{
        if (Input.GetKeyDown(KeyCode.LeftArrow)  || Input.GetKeyDown(KeyCode.A)) SwitchLane(-1);
        if (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.D)) SwitchLane(1);
        float newX = Mathf.MoveTowards(transform.position.x, targetX, laneSpeed * Time.deltaTime);
        rb.velocity = new Vector3((newX - transform.position.x) / Time.deltaTime, rb.velocity.y, runSpeed);
    }}
    void SwitchLane(int dir)
    {{
        int next = Mathf.Clamp(currentLane + dir, 0, lanePositions.Length - 1);
        currentLane = next; targetX = lanePositions[currentLane];
    }}
    void OnTriggerEnter(Collider other)
    {{
        if (other.CompareTag("Obstacle")) FindObjectOfType<GameManager>()?.GameOver();
    }}
}}"""

UNIVERSAL_TEMPLATES["quiz"] = """using UnityEngine;
using System.Collections.Generic;
[System.Serializable]
public class Question {{ public string text; public string[] answers; public int correctIndex; }}
public class {name} : MonoBehaviour
{{
    public List<Question> questions = new List<Question>();
    public int score = 0;
    private int currentIndex = 0;
    public Question GetCurrentQuestion() {{ return currentIndex < questions.Count ? questions[currentIndex] : null; }}
    public bool Answer(int index)
    {{
        if (currentIndex >= questions.Count) return false;
        bool correct = index == questions[currentIndex].correctIndex;
        if (correct) score++;
        currentIndex++;
        return correct;
    }}
    public bool IsFinished() {{ return currentIndex >= questions.Count; }}
    public int GetScore() {{ return score; }}
}}"""

UNIVERSAL_TEMPLATES["auto_battle"] = """using UnityEngine;
using System.Collections;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    [Header("Auto Battle")]
    public List<GameObject> playerUnits = new List<GameObject>();
    public List<GameObject> enemyUnits  = new List<GameObject>();
    public float battleSpeed = 1f;
    private bool battleActive = false;
    public void StartBattle()
    {{
        battleActive = true;
        StartCoroutine(BattleLoop());
    }}
    IEnumerator BattleLoop()
    {{
        while (battleActive && playerUnits.Count > 0 && enemyUnits.Count > 0)
        {{
            yield return new WaitForSeconds(1f / battleSpeed);
            // Each player unit attacks random enemy
            foreach (var unit in new List<GameObject>(playerUnits))
            {{
                if (enemyUnits.Count == 0) break;
                var target = enemyUnits[Random.Range(0, enemyUnits.Count)];
                var hb = target?.GetComponent<HealthBar>();
                if (hb != null) hb.TakeDamage(10);
            }}
            enemyUnits.RemoveAll(u => u == null || !u.activeInHierarchy);
            playerUnits.RemoveAll(u => u == null || !u.activeInHierarchy);
        }}
        battleActive = false;
        print(playerUnits.Count > 0 ? "Player wins!" : "Enemy wins!");
    }}
}}"""

UNIVERSAL_TEMPLATES["flight"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Flight")]
    public float thrust = 20f;
    public float turnSpeed = 60f;
    public float pitchSpeed = 45f;
    public float maxSpeed = 50f;
    private Rigidbody rb;
    void Start() {{ rb = GetComponent<Rigidbody>(); rb.useGravity = false; }}
    void FixedUpdate()
    {{
        float yaw   = Input.GetAxis("Horizontal") * turnSpeed * Time.fixedDeltaTime;
        float pitch = Input.GetAxis("Vertical")   * pitchSpeed * Time.fixedDeltaTime;
        float thrustInput = Input.GetKey(KeyCode.Space) ? 1f : 0.2f;
        transform.Rotate(pitch, yaw, 0f, Space.Self);
        Vector3 vel = transform.forward * thrust * thrustInput;
        rb.velocity = Vector3.ClampMagnitude(vel, maxSpeed);
    }}
    void OnTriggerEnter(Collider other)
    {{
        if (other.CompareTag("Enemy")) FindObjectOfType<GameManager>()?.OnEnemyKilled();
    }}
}}"""


TEMPLATED_ROLES = {
    # Original
    "spawner","manager","ui","health","background","collectible","projectile",
    "gem","board","powerup","enemy","player","vehicle","opponent","generic","game_manager",
    # Card Games
    "card","deck","hand",
    # Horror
    "horror_enemy","flashlight","jumpscare",
    # VR
    "vr_player","vr_grab",
    # AR
    "ar_manager",
    # Simulation
    "day_night","weather","physics_sim",
    # RPG Systems
    "inventory","dialogue","quest","save_system",
    # Utility
    "audio_manager","camera_controller","touch_input","pathfinding",
    "minimap","interaction","scene_manager","leaderboard","state_machine",
    "npc","procedural_map","object_pool","timer","ragdoll",
    # Hyper/Fighting
    "hyper_casual","fighting",
    # Puzzle
    "puzzle_grid","match3","sokoban","sliding_puzzle","lock_puzzle","physics_puzzle",
    # Tower Defense
    "tower","tower_bullet","wave_manager","path_follower",
    # Strategy/RTS
    "rts_unit","resource_manager",
    # Sports
    "ball_physics","scoreboard",
    # Rhythm/Music
    "rhythm_lane",
    # Idle/Clicker
    "idle_manager",
    # Stealth
    "guard_ai","stealth_player",
    # Racing Extended
    "lap_manager",
    # Platformer Extended
    "platformer_player","checkpoint_system",
    # Tycoon/City Builder
    "building",
    # Farming/Survival
    "farmable","hunger_thirst",
    # Multiplayer
    "network_player",
    # Bullet Hell
    "bullet_pattern",
    # Gacha
    "gacha_system",
    # Escape Room
    "puzzle_trigger",
}

# Extended keyword → role mapping for planner
ROLE_KEYWORD_MAP = {
    # Card games
    "card":         ["card","playing","deck","hand","poker","solitaire","blackjack","koutchina"],
    "deck":         ["deck","shuffle"],
    "hand":         ["hand","hold"],
    # Horror
    "horror_enemy": ["horror","ghost","monster","zombie","creature","stalker","demon"],
    "flashlight":   ["flashlight","torch","light","lamp"],
    "jumpscare":    ["jumpscare","scare","fright"],
    # VR
    "vr_player":    ["vr","virtual reality","xr","oculus","quest"],
    "vr_grab":      ["grab","pick up","hold","interact vr"],
    # AR
    "ar_manager":   ["ar","augmented reality","arkit","arcore","place"],
    # Simulation
    "day_night":    ["day","night","cycle","sun","time of day"],
    "weather":      ["weather","rain","snow","fog","storm","climate"],
    "physics_sim":  ["physics","simulation","sim","rigid","destructible","break"],
    # RPG
    "inventory":    ["inventory","items","loot","equipment","bag"],
    "dialogue":     ["dialogue","dialog","conversation","talk","npc talk"],
    "quest":        ["quest","mission","task","objective"],
    "save_system":  ["save","load","checkpoint","persist"],
    # Utility
    "audio_manager":["audio","sound","music","sfx","mixer"],
    "camera_controller":["camera","cam","follow","orbit","shake"],
    "touch_input":  ["touch","swipe","tap","mobile input","pinch"],
    "pathfinding":  ["pathfinding","path","astar","navigate","movement ai"],
    "minimap":      ["minimap","map","radar"],
    "interaction":  ["interact","press e","pickup","use","trigger"],
    "scene_manager":["scene","transition","load scene","level change","fade"],
    "leaderboard":  ["leaderboard","highscore","ranking","score board"],
    "state_machine":["state machine","fsm","states","ai state"],
    "npc":          ["npc","villager","civilian","shopkeeper","friendly"],
    "procedural_map":["procedural","random map","dungeon","maze","generate level"],
    "object_pool":  ["pool","object pool","bullets pool","performance"],
    "timer":        ["timer","countdown","stopwatch","time limit"],
    "ragdoll":      ["ragdoll","death physics","rag","collapse"],
    "hyper_casual":  ["hyper casual","one touch","runner","lane","swipe run"],
    "fighting":      ["fighting","fighter","street fighter","punch","kick","combat"],
    # Puzzle
    "puzzle_grid":   ["puzzle grid","grid puzzle","tile puzzle"],
    "match3":        ["match 3","match3","match-3","gem","bejeweled","candy crush"],
    "sokoban":       ["sokoban","box push","push puzzle"],
    "sliding_puzzle":["sliding puzzle","15 puzzle","8 puzzle","tile slide"],
    "lock_puzzle":   ["lock","combination","code lock","cipher"],
    "physics_puzzle":["physics puzzle","angry birds","cut the rope","catapult"],
    # Tower Defense
    "tower":         ["tower","turret","defense building","tower defense"],
    "tower_bullet":  ["tower bullet","turret bullet"],
    "wave_manager":  ["wave","waves","enemy wave","tower defense manager"],
    "path_follower": ["path follow","waypoint enemy","td enemy"],
    # Strategy/RTS
    "rts_unit":      ["rts","unit","soldier","strategy","real time strategy"],
    "resource_manager":["resource","gold","wood","stone","currency","tycoon","rts resource"],
    # Sports
    "ball_physics":  ["ball","football","basketball","tennis","golf","soccer"],
    "scoreboard":    ["scoreboard","score board","team score","match score"],
    # Rhythm
    "rhythm_lane":   ["rhythm","music game","guitar hero","piano tiles","beat","lane"],
    # Idle
    "idle_manager":  ["idle","clicker","incremental","cookie clicker","idle game"],
    # Stealth
    "guard_ai":      ["guard","security","patrol","stealth ai","vision cone"],
    "stealth_player":["stealth player","sneak","crouch","hide"],
    # Racing
    "lap_manager":   ["lap","race lap","checkpoint race","racing manager"],
    # Platformer
    "platformer_player":["platformer","jump","coyote","double jump","wall jump"],
    "checkpoint_system":["checkpoint","respawn","lives","spawn point"],
    # Tycoon
    "building":      ["building","construct","tycoon building","city building","shop"],
    # Farming/Survival
    "farmable":      ["farm","crop","plant","harvest","grow","farming"],
    "hunger_thirst": ["hunger","thirst","stamina","survival needs","starvation"],
    # Multiplayer
    "network_player":["multiplayer","network","online","mirror","photon","netcode"],
    # Bullet Hell
    "bullet_pattern":["bullet hell","danmaku","shmup","shoot em up","bullet pattern"],
    # Gacha
    "gacha_system":  ["gacha","loot box","summon","pull","random reward","gacha game"],
    # Escape Room
    "puzzle_trigger":["escape room","puzzle chain","sequence puzzle","room puzzle"],
    # MOBA
    "moba_hero":     ["moba","league","dota","hero","ability","moba game","aoe skill"],
    "moba_tower":    ["moba tower","inhibitor","nexus","moba base"],
    # Battle Royale
    "zone_shrink":   ["battle royale","pubg","fortnite","zone","safe zone","shrink","br game"],
    "loot_spawner":  ["loot","drop","random item","chest loot","loot table"],
    # Roguelike
    "roguelike_room":["roguelike","roguelite","dungeon run","rogue","random room","run"],
    "roguelike_stat":["stat upgrade","level up","perk","relic","artifact","rogue upgrade"],
    # Metroidvania
    "ability_gate":  ["metroidvania","ability unlock","gate","skill gate","locked door"],
    "ability_system":["ability","dash","grapple","double jump unlock","power unlock"],
    # Dating Sim / Visual Novel
    "vn_manager":    ["visual novel","dating sim","dialogue tree","affection","route"],
    "affection":     ["affection","relationship","romance","hearts","friendship"],
    # Beat em up / Hack and Slash
    "combo_system":  ["beat em up","hack and slash","combo","brawler","street beat","punch combo"],
    "enemy_group":   ["enemy group","wave attack","gang","brawler enemy","mob"],
    # Fishing
    "fishing":       ["fishing","fish","rod","reel","catch","bait","fishing game"],
    # Cooking
    "cooking":       ["cooking","recipe","chef","kitchen","food","ingredient","restaurant"],
    # Sandbox / Building (Minecraft-style)
    "block_place":   ["minecraft","sandbox","voxel","block","place block","destroy block","build sandbox"],
    "crafting":      ["crafting","craft","recipe craft","workbench","forge"],
    # Naval / Pirate
    "ship_combat":   ["naval","ship combat","pirate","cannon","sea battle","ocean fight"],
    "boat":          ["boat","ship","vessel","sail","pirate ship","galleon"],
    # Flight
    "flight":        ["flight","airplane","plane","pilot","fly","dogfight","aircraft"],
    # Mech / Robot
    "mech":          ["mech","robot","gundam","mecha","giant robot","exosuit"],
    # Hunting
    "hunting":       ["hunting","hunt","prey","tracker","wilderness","deer","animal hunt"],
    # Dungeon Crawler
    "dungeon_room":  ["dungeon crawler","dungeon","crawler","floor","boss room","dungeon room"],
    "loot_drop":     ["drop loot","item drop","drop rate","enemy drop","reward drop"],
    # Castle / Siege
    "siege":         ["siege","castle","catapult","wall","gate","fortress","siege engine"],
    "castle_gate":   ["gate","drawbridge","portcullis","castle entrance"],
    # Space Sim
    "space_ship":    ["space sim","spaceship","starfighter","galaxy sim","orbit","asteroid"],
    "gravity":       ["gravity","orbit","zero gravity","black hole","planet gravity"],
    # Battle Simulator
    "unit_ai":       ["battle sim","simulator","unit battle","army","formation","battle simulator"],
    # Party Game
    "minigame":      ["party game","minigame","mini-game","party","1vs1","couch coop"],
    # Educational
    "quiz":          ["quiz","question","answer","educational","trivia","multiple choice"],
    "edu_score":     ["education","learn","kids","children","school game"],
    # Card Game (advanced - like Hearthstone)
    "card_battle":   ["card game","card battle","hearthstone","gwent","slay the spire"],
    "mana_system":   ["mana","energy","card cost","resource card"],
    # Endless Runner
    "lane_switcher": ["endless runner","temple run","subway","lane switch","swipe lane"],
    "obstacle":      ["obstacle","barrier","hurdle","jump over","dodge"],
    # Kart Racing
    "kart":          ["kart","mario kart","kart race","item box","kart boost"],
    "race_item":     ["race item","blue shell","boost item","weapon race","power up race"],
    # Cyberpunk / Sci-fi
    "hacking":       ["hack","hacking","cyberpunk","matrix","network intrusion","cyber"],
    # Underwater
    "underwater":    ["underwater","submarine","diving","ocean","deep sea","swim","aquatic"],
    # Shooting Gallery
    "shooting_gallery":["shooting gallery","duck hunt","target practice","gallery shoot"],
    # Survival Horror
    "monster_ai":    ["survival horror","monster","creature","horror ai","fear","jump scare"],
    "flashlight_battery":["battery","flashlight","light","darkness","torch","power"],
    # Point and Click
    "inventory_item":["point and click","adventure game","item use","combine items"],
    # Auto-battler / Auto Chess
    "auto_battle":   ["auto battler","auto chess","auto fight","synergy","bench"],
    # Incremental / Clicker
    "click_upgrade": ["clicker","tap","prestige","upgrade shop","auto clicker"],
}


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
UNIVERSAL_TEMPLATES["game_manager"] = """using UnityEngine;
using UnityEngine.SceneManagement;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}

    [Header("Game State")]
    public int score = 0;
    public int lives = 3;
    public bool isGameOver = false;
    public bool isPaused = false;

    [Header("Settings")]
    public int scorePerKill = 100;
    public int nextSceneIndex = 1;

    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else {{ Destroy(gameObject); return; }}
        Time.timeScale = 1f;
    }}

    public void AddScore(int amount)
    {{
        score += amount;
        Debug.Log("Score: " + score);
    }}

    public void OnEnemyKilled() {{ AddScore(scorePerKill); }}

    public void LoseLife()
    {{
        lives = Mathf.Max(0, lives - 1);
        Debug.Log("Lives: " + lives);
        if (lives <= 0) GameOver();
    }}

    public void GameOver()
    {{
        if (isGameOver) return;
        isGameOver = true;
        Time.timeScale = 0f;
        Debug.Log("Game Over! Score: " + score);
    }}

    public void Win()
    {{
        Time.timeScale = 0f;
        Debug.Log("You Win! Score: " + score);
    }}

    public void RestartGame()
    {{
        isGameOver = false;
        Time.timeScale = 1f;
        SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
    }}

    public void NextLevel() {{ SceneManager.LoadScene(nextSceneIndex); }}

    public void TogglePause()
    {{
        if (isGameOver) return;
        isPaused = !isPaused;
        Time.timeScale = isPaused ? 0f : 1f;
    }}
}}"""


# ── SaveSystem + more missing Unity templates ──────────────────

UNIVERSAL_TEMPLATES["save_system"] = """using UnityEngine;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;
[System.Serializable]
public class SaveData
{{
    public int score;
    public int level;
    public float[] playerPosition = new float[3];
    public int lives;
    public string[] unlockedAbilities;
}}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    private static string SavePath => Application.persistentDataPath + "/save.dat";
    void Awake() {{ if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }} else Destroy(gameObject); }}
    public void Save(SaveData data)
    {{
        try {{
            BinaryFormatter bf = new BinaryFormatter();
            using (FileStream fs = File.Open(SavePath, FileMode.Create))
                bf.Serialize(fs, data);
            Debug.Log("Game saved!");
        }} catch (System.Exception e) {{ Debug.LogError("Save failed: " + e.Message); }}
    }}
    public SaveData Load()
    {{
        if (!File.Exists(SavePath)) return new SaveData();
        try {{
            BinaryFormatter bf = new BinaryFormatter();
            using (FileStream fs = File.Open(SavePath, FileMode.Open))
                return (SaveData)bf.Deserialize(fs);
        }} catch {{ return new SaveData(); }}
    }}
    public void DeleteSave() {{ if (File.Exists(SavePath)) File.Delete(SavePath); }}
    public bool HasSave() {{ return File.Exists(SavePath); }}
}}"""

UNIVERSAL_TEMPLATES["dialogue"] = """using UnityEngine;
using System.Collections.Generic;
using TMPro;
[System.Serializable]
public class DialogueLine {{ public string speaker; [TextArea] public string text; }}
public class {name} : MonoBehaviour
{{
    public List<DialogueLine> lines = new List<DialogueLine>();
    public TextMeshProUGUI speakerText;
    public TextMeshProUGUI dialogueText;
    public GameObject dialoguePanel;
    private int currentIndex = 0;
    private bool isActive = false;
    public void StartDialogue()
    {{
        if (lines.Count == 0) return;
        currentIndex = 0; isActive = true;
        if (dialoguePanel != null) dialoguePanel.SetActive(true);
        ShowLine();
    }}
    public void NextLine()
    {{
        currentIndex++;
        if (currentIndex >= lines.Count) EndDialogue();
        else ShowLine();
    }}
    void ShowLine()
    {{
        if (currentIndex >= lines.Count) return;
        DialogueLine line = lines[currentIndex];
        if (speakerText != null)  speakerText.text  = line.speaker;
        if (dialogueText != null) dialogueText.text = line.text;
    }}
    void EndDialogue()
    {{
        isActive = false;
        if (dialoguePanel != null) dialoguePanel.SetActive(false);
    }}
    void Update() {{ if (isActive && Input.GetButtonDown("Fire1")) NextLine(); }}
}}"""

UNIVERSAL_TEMPLATES["inventory"] = """using UnityEngine;
using System.Collections.Generic;
[System.Serializable]
public class Item {{ public string name; public int quantity; public Sprite icon; public string description; }}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public List<Item> items = new List<Item>();
    public int maxSlots = 20;
    void Awake() {{ if (Instance == null) Instance = this; else Destroy(gameObject); }}
    public bool AddItem(Item newItem)
    {{
        Item existing = items.Find(i => i.name == newItem.name);
        if (existing != null) {{ existing.quantity += newItem.quantity; return true; }}
        if (items.Count >= maxSlots) {{ Debug.Log("Inventory full!"); return false; }}
        items.Add(newItem); return true;
    }}
    public bool RemoveItem(string itemName, int amount = 1)
    {{
        Item item = items.Find(i => i.name == itemName);
        if (item == null || item.quantity < amount) return false;
        item.quantity -= amount;
        if (item.quantity <= 0) items.Remove(item);
        return true;
    }}
    public bool HasItem(string itemName, int amount = 1)
    {{
        Item item = items.Find(i => i.name == itemName);
        return item != null && item.quantity >= amount;
    }}
    public int GetItemCount(string itemName) {{ Item i = items.Find(x => x.name == itemName); return i?.quantity ?? 0; }}
}}"""

UNIVERSAL_TEMPLATES["quest"] = """using UnityEngine;
using System.Collections.Generic;
[System.Serializable]
public class Quest
{{
    public string questName;
    public string description;
    public int requiredKills;
    public int currentKills;
    public int rewardScore;
    public bool isComplete;
    public bool isActive;
}}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public List<Quest> quests = new List<Quest>();
    void Awake() {{ if (Instance == null) Instance = this; else Destroy(gameObject); }}
    public void StartQuest(int index) {{ if (index < quests.Count) quests[index].isActive = true; }}
    public void UpdateKillProgress(int index, int amount = 1)
    {{
        if (index >= quests.Count || !quests[index].isActive) return;
        quests[index].currentKills += amount;
        if (quests[index].currentKills >= quests[index].requiredKills) CompleteQuest(index);
    }}
    void CompleteQuest(int index)
    {{
        quests[index].isComplete = true; quests[index].isActive = false;
        GameManager.Instance?.AddScore(quests[index].rewardScore);
        Debug.Log($"Quest complete: {{quests[index].questName}}");
    }}
    public bool IsComplete(int index) {{ return index < quests.Count && quests[index].isComplete; }}
}}"""

UNIVERSAL_TEMPLATES["day_night"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Day/Night")]
    public Light directionalLight;
    public float dayDuration = 120f;
    public Gradient sunColor;
    public AnimationCurve sunIntensity;
    [Range(0,1)] public float timeOfDay = 0.25f;
    void Update()
    {{
        timeOfDay += Time.deltaTime / dayDuration;
        if (timeOfDay >= 1f) timeOfDay = 0f;
        float angle = timeOfDay * 360f - 90f;
        if (directionalLight != null)
        {{
            directionalLight.transform.rotation = Quaternion.Euler(angle, 170f, 0f);
            directionalLight.color = sunColor.Evaluate(timeOfDay);
            directionalLight.intensity = sunIntensity.Evaluate(timeOfDay);
        }}
    }}
    public bool IsDay()   {{ return timeOfDay > 0.25f && timeOfDay < 0.75f; }}
    public bool IsNight() {{ return !IsDay(); }}
    public float GetHour() {{ return timeOfDay * 24f; }}
}}"""

UNIVERSAL_TEMPLATES["minimap"] = """using UnityEngine;
using UnityEngine.UI;
public class {name} : MonoBehaviour
{{
    [Header("Minimap")]
    public Camera minimapCamera;
    public Transform player;
    public RawImage minimapImage;
    public float height = 20f;
    public float mapSize = 50f;
    void LateUpdate()
    {{
        if (player == null || minimapCamera == null) return;
        Vector3 pos = player.position;
        minimapCamera.transform.position = new Vector3(pos.x, pos.y + height, pos.z);
        minimapCamera.orthographicSize = mapSize;
    }}
    public void SetTarget(Transform t) {{ player = t; }}
}}"""

UNIVERSAL_TEMPLATES["object_pool"] = """using UnityEngine;
using System.Collections.Generic;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    [System.Serializable]
    public class Pool {{ public string tag; public GameObject prefab; public int size; }}
    public List<Pool> pools = new List<Pool>();
    private Dictionary<string, Queue<GameObject>> poolDictionary = new Dictionary<string, Queue<GameObject>>();
    void Awake() {{ if (Instance == null) Instance = this; else Destroy(gameObject); }}
    void Start()
    {{
        foreach (Pool pool in pools)
        {{
            Queue<GameObject> q = new Queue<GameObject>();
            for (int i = 0; i < pool.size; i++)
            {{
                GameObject obj = Instantiate(pool.prefab, transform);
                obj.SetActive(false); q.Enqueue(obj);
            }}
            poolDictionary[pool.tag] = q;
        }}
    }}
    public GameObject Spawn(string tag, Vector3 pos, Quaternion rot)
    {{
        if (!poolDictionary.ContainsKey(tag)) return null;
        GameObject obj = poolDictionary[tag].Dequeue();
        obj.SetActive(true); obj.transform.SetPositionAndRotation(pos, rot);
        poolDictionary[tag].Enqueue(obj);
        return obj;
    }}
}}"""

UNIVERSAL_TEMPLATES["scene_manager"] = """using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public GameObject loadingScreen;
    public UnityEngine.UI.Slider progressBar;
    void Awake() {{ if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }} else Destroy(gameObject); }}
    public void LoadScene(string sceneName) {{ StartCoroutine(LoadAsync(sceneName)); }}
    public void LoadScene(int index)         {{ StartCoroutine(LoadAsync(index)); }}
    public void ReloadCurrent()              {{ LoadScene(SceneManager.GetActiveScene().name); }}
    IEnumerator LoadAsync(object scene)
    {{
        if (loadingScreen != null) loadingScreen.SetActive(true);
        AsyncOperation op = scene is string s ? SceneManager.LoadSceneAsync(s) : SceneManager.LoadSceneAsync((int)scene);
        op.allowSceneActivation = false;
        while (!op.isDone)
        {{
            float progress = Mathf.Clamp01(op.progress / 0.9f);
            if (progressBar != null) progressBar.value = progress;
            if (op.progress >= 0.9f) op.allowSceneActivation = true;
            yield return null;
        }}
        if (loadingScreen != null) loadingScreen.SetActive(false);
    }}
}}"""

UNIVERSAL_TEMPLATES["state_machine"] = """using UnityEngine;
public enum GameState {{ Menu, Playing, Paused, GameOver, Win }}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public GameState CurrentState {{ get; private set; }} = GameState.Menu;
    public delegate void StateChanged(GameState oldState, GameState newState);
    public event StateChanged OnStateChanged;
    void Awake() {{ if (Instance == null) Instance = this; else Destroy(gameObject); }}
    public void ChangeState(GameState newState)
    {{
        GameState old = CurrentState;
        CurrentState = newState;
        OnStateChanged?.Invoke(old, newState);
        HandleStateChange(newState);
    }}
    void HandleStateChange(GameState state)
    {{
        switch (state)
        {{
            case GameState.Playing:  Time.timeScale = 1f; break;
            case GameState.Paused:   Time.timeScale = 0f; break;
            case GameState.GameOver: Time.timeScale = 0f; break;
            case GameState.Win:      Time.timeScale = 0f; break;
        }}
    }}
    public bool IsPlaying()  {{ return CurrentState == GameState.Playing; }}
    public bool IsPaused()   {{ return CurrentState == GameState.Paused; }}
    public bool IsGameOver() {{ return CurrentState == GameState.GameOver; }}
}}"""

UNIVERSAL_TEMPLATES["audio_manager"] = """using UnityEngine;
using System.Collections.Generic;
[System.Serializable]
public class Sound {{ public string name; public AudioClip clip; [Range(0,1)] public float volume = 1f; [Range(0.5f,1.5f)] public float pitch = 1f; public bool loop; [HideInInspector] public AudioSource source; }}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public List<Sound> sounds = new List<Sound>();
    void Awake()
    {{
        if (Instance == null) {{ Instance = this; DontDestroyOnLoad(gameObject); }}
        else {{ Destroy(gameObject); return; }}
        foreach (Sound s in sounds) {{
            s.source = gameObject.AddComponent<AudioSource>();
            s.source.clip = s.clip; s.source.volume = s.volume;
            s.source.pitch = s.pitch; s.source.loop = s.loop;
        }}
    }}
    public void Play(string name)   {{ Sound s = sounds.Find(x => x.name == name); if (s != null) s.source.Play(); }}
    public void Stop(string name)   {{ Sound s = sounds.Find(x => x.name == name); if (s != null) s.source.Stop(); }}
    public void Pause(string name)  {{ Sound s = sounds.Find(x => x.name == name); if (s != null) s.source.Pause(); }}
    public bool IsPlaying(string name) {{ Sound s = sounds.Find(x => x.name == name); return s != null && s.source.isPlaying; }}
    public void SetVolume(string name, float vol) {{ Sound s = sounds.Find(x => x.name == name); if (s != null) s.source.volume = vol; }}
}}"""

UNIVERSAL_TEMPLATES["camera_controller"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Target")]
    public Transform target;
    public Vector3 offset = new Vector3(0, 5, -10);
    [Header("Settings")]
    public float smoothSpeed = 5f;
    public float rotationSpeed = 3f;
    public bool followRotation = false;
    [Header("Shake")]
    private float shakeDuration = 0f;
    private float shakeMagnitude = 0.1f;
    void LateUpdate()
    {{
        if (target == null) return;
        Vector3 desired = target.position + (followRotation ? target.TransformDirection(offset) : offset);
        transform.position = Vector3.Lerp(transform.position, desired, smoothSpeed * Time.deltaTime);
        if (followRotation) transform.LookAt(target);
        if (shakeDuration > 0)
        {{
            transform.position += Random.insideUnitSphere * shakeMagnitude;
            shakeDuration -= Time.deltaTime;
        }}
    }}
    public void Shake(float duration, float magnitude = 0.1f)
    {{
        shakeDuration = duration; shakeMagnitude = magnitude;
    }}
}}"""

UNIVERSAL_TEMPLATES["leaderboard"] = """using UnityEngine;
using System.Collections.Generic;
using System.Linq;
[System.Serializable]
public class ScoreEntry {{ public string playerName; public int score; public float time; }}
public class {name} : MonoBehaviour
{{
    public static {name} Instance {{ get; private set; }}
    public List<ScoreEntry> entries = new List<ScoreEntry>();
    public int maxEntries = 10;
    void Awake() {{ if (Instance == null) Instance = this; else Destroy(gameObject); Load(); }}
    public void AddScore(string name, int score, float time = 0)
    {{
        entries.Add(new ScoreEntry {{ playerName = name, score = score, time = time }});
        entries = entries.OrderByDescending(e => e.score).Take(maxEntries).ToList();
        Save();
    }}
    public List<ScoreEntry> GetTop(int n = 10) {{ return entries.Take(n).ToList(); }}
    public int GetRank(int score) {{ return entries.Count(e => e.score > score) + 1; }}
    void Save() {{ PlayerPrefs.SetString("Leaderboard", JsonUtility.ToJson(this)); PlayerPrefs.Save(); }}
    void Load() {{ string data = PlayerPrefs.GetString("Leaderboard",""); if (!string.IsNullOrEmpty(data)) JsonUtility.FromJsonOverwrite(data, this); }}
}}"""

UNIVERSAL_TEMPLATES["interaction"] = """using UnityEngine;
using TMPro;
public interface IInteractable {{ void Interact(GameObject player); string GetPrompt(); }}
public class {name} : MonoBehaviour
{{
    [Header("Interaction")]
    public float interactRadius = 2f;
    public LayerMask interactLayer;
    public KeyCode interactKey = KeyCode.E;
    public TextMeshProUGUI promptText;
    private IInteractable currentTarget;
    void Update()
    {{
        Collider[] cols = Physics.OverlapSphere(transform.position, interactRadius, interactLayer);
        currentTarget = null;
        foreach (var col in cols)
        {{
            IInteractable inter = col.GetComponent<IInteractable>();
            if (inter != null) {{ currentTarget = inter; break; }}
        }}
        if (promptText != null)
        {{
            promptText.gameObject.SetActive(currentTarget != null);
            if (currentTarget != null) promptText.text = currentTarget.GetPrompt();
        }}
        if (currentTarget != null && Input.GetKeyDown(interactKey))
            currentTarget.Interact(gameObject);
    }}
}}"""

UNIVERSAL_TEMPLATES["touch_input"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Touch Settings")]
    public float swipeThreshold = 50f;
    public float tapMaxTime = 0.2f;
    private Vector2 touchStart;
    private float touchStartTime;
    public delegate void SwipeAction(Vector2 direction);
    public static event SwipeAction OnSwipe;
    public static event System.Action OnTap;
    void Update()
    {{
        if (Input.touchCount == 0) return;
        Touch touch = Input.GetTouch(0);
        if (touch.phase == TouchPhase.Began) {{ touchStart = touch.position; touchStartTime = Time.time; }}
        if (touch.phase == TouchPhase.Ended)
        {{
            Vector2 delta = touch.position - touchStart;
            float duration = Time.time - touchStartTime;
            if (delta.magnitude < swipeThreshold && duration < tapMaxTime) OnTap?.Invoke();
            else if (delta.magnitude >= swipeThreshold) OnSwipe?.Invoke(delta.normalized);
        }}
    }}
}}"""

UNIVERSAL_TEMPLATES["npc"] = """using UnityEngine;
using System.Collections;
public class {name} : MonoBehaviour
{{
    [Header("NPC")]
    public string npcName = "NPC";
    public float walkSpeed = 2f;
    public float waypointWaitTime = 2f;
    public Transform[] waypoints;
    private int currentWaypoint = 0;
    private bool isWaiting = false;
    void Update()
    {{
        if (waypoints.Length == 0 || isWaiting) return;
        Transform wp = waypoints[currentWaypoint];
        transform.position = Vector3.MoveTowards(transform.position, wp.position, walkSpeed * Time.deltaTime);
        transform.LookAt(new Vector3(wp.position.x, transform.position.y, wp.position.z));
        if (Vector3.Distance(transform.position, wp.position) < 0.1f) StartCoroutine(WaitAtWaypoint());
    }}
    IEnumerator WaitAtWaypoint()
    {{
        isWaiting = true;
        yield return new WaitForSeconds(waypointWaitTime);
        currentWaypoint = (currentWaypoint + 1) % waypoints.Length;
        isWaiting = false;
    }}
    public void TalkTo() {{ Debug.Log($"{{npcName}}: Hello, traveler!"); }}
}}"""

UNIVERSAL_TEMPLATES["procedural_map"] = """using UnityEngine;
public class {name} : MonoBehaviour
{{
    [Header("Map")]
    public int width = 20;
    public int height = 20;
    [Range(0,1)] public float wallChance = 0.3f;
    public int smoothIterations = 5;
    public GameObject wallPrefab;
    public GameObject floorPrefab;
    private int[,] map;
    void Start() {{ Generate(); }}
    public void Generate()
    {{
        map = new int[width, height];
        System.Random rng = new System.Random();
        // Fill randomly
        for (int x = 0; x < width; x++)
            for (int y = 0; y < height; y++)
                map[x,y] = (x==0||x==width-1||y==0||y==height-1) ? 1 : (rng.NextDouble() < wallChance ? 1 : 0);
        // Smooth
        for (int i = 0; i < smoothIterations; i++) Smooth();
        BuildMesh();
    }}
    void Smooth()
    {{
        int[,] newMap = (int[,])map.Clone();
        for (int x=1;x<width-1;x++) for (int y=1;y<height-1;y++)
        {{
            int n = CountNeighbours(x,y);
            if (n > 4) newMap[x,y] = 1; else if (n < 4) newMap[x,y] = 0;
        }}
        map = newMap;
    }}
    int CountNeighbours(int x, int y) {{ int c=0; for(int nx=-1;nx<=1;nx++) for(int ny=-1;ny<=1;ny++) if(nx!=0||ny!=0) c+=map[x+nx,y+ny]; return c; }}
    void BuildMesh()
    {{
        foreach (Transform child in transform) Destroy(child.gameObject);
        for (int x=0;x<width;x++) for (int y=0;y<height;y++)
        {{
            GameObject prefab = map[x,y]==1 ? wallPrefab : floorPrefab;
            if (prefab != null) Instantiate(prefab, new Vector3(x,0,y), Quaternion.identity, transform);
        }}
    }}
}}"""
