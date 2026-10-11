Here is the quick guide to turn the entire system **OFF** and turn it back **ON**.

---

###  How to Turn It OFF

#### Step 1: Stop the Running Processes
In each of the terminal windows running the processes, press:
```text
Ctrl + C
```
1. In the **Dashboard** terminal $\to$ `Ctrl + C`
2. In the **Producer** terminal $\to$ `Ctrl + C`
3. In the **Streaming Scorer** terminal $\to$ `Ctrl + C`

#### Step 2: Shut Down Docker (Kafka & MinIO)
In any terminal inside the project directory, run:
```bash
make infra-down
```
*(This stops and removes the Kafka and MinIO containers).*

---

###  How to Turn It ON

Whenever you want to start the system again:

#### Step 1: Start Docker Infrastructure
```bash
cd "/home/hemanth_ubuntu/7th sem/bda/fraud-detection-system"
make infra-up
```
*(Starts Kafka and MinIO in the background).*

#### Step 2 (Optional): Reset Previous Run Data
If you want a fresh demo with zero previous transactions on the dashboard, run:
```bash
rm -rf data/outputs/checkpoints
rm -rf data/outputs/predictions/_spark_metadata data/outputs/alerts/_spark_metadata
rm -f data/outputs/predictions/*.parquet data/outputs/predictions/*.crc
rm -f data/outputs/alerts/*.parquet data/outputs/alerts/*.crc
```

#### Step 3: Launch the 3 Components
Open 3 separate terminals, make sure you are in the project folder (`cd "/home/hemanth_ubuntu/7th sem/bda/fraud-detection-system"`), and run:

* **Terminal 1 (The Scorer):**
  ```bash
  make stream
  ```
* **Terminal 2 (The Producer):**
  ```bash
  make produce
  ```
* **Terminal 3 (The Dashboard):**
  ```bash
  make dashboard
  ```
  Then open **`http://localhost:8501`** in your browser.Here is the quick guide to turn the entire system **OFF** and turn it back **ON**.

---

###  How to Turn It OFF

#### Step 1: Stop the Running Processes
In each of the terminal windows running the processes, press:
```text
Ctrl + C
```
1. In the **Dashboard** terminal $\to$ `Ctrl + C`
2. In the **Producer** terminal $\to$ `Ctrl + C`
3. In the **Streaming Scorer** terminal $\to$ `Ctrl + C`

#### Step 2: Shut Down Docker (Kafka & MinIO)
In any terminal inside the project directory, run:
```bash
make infra-down
```
*(This stops and removes the Kafka and MinIO containers).*

---

###  How to Turn It ON

Whenever you want to start the system again:

#### Step 1: Start Docker Infrastructure
```bash
cd "/home/hemanth_ubuntu/7th sem/bda/fraud-detection-system"
make infra-up
```
*(Starts Kafka and MinIO in the background).*

#### Step 2 (Optional): Reset Previous Run Data
If you want a fresh demo with zero previous transactions on the dashboard, run:
```bash
rm -rf data/outputs/checkpoints
rm -rf data/outputs/predictions/_spark_metadata data/outputs/alerts/_spark_metadata
rm -f data/outputs/predictions/*.parquet data/outputs/predictions/*.crc
rm -f data/outputs/alerts/*.parquet data/outputs/alerts/*.crc
```

#### Step 3: Launch the 3 Components
Open 3 separate terminals, make sure you are in the project folder (`cd "/home/hemanth_ubuntu/7th sem/bda/fraud-detection-system"`), and run:

* **Terminal 1 (The Scorer):**
  ```bash
  make stream
  ```
* **Terminal 2 (The Producer):**
  ```bash
  make produce
  ```
* **Terminal 3 (The Dashboard):**
  ```bash
  make dashboard
  ```
  Then open **`http://localhost:8501`** in your browser.