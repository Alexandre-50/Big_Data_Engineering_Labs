# Module 06 – Containerization and Kubernetes : réponses aux labs

Environnement : Windows 11, Docker Desktop 29.1.3, minikube v1.39.0 (driver Docker, runtime containerd), Kubernetes v1.37.0.

---

## Lab 1 – Kubernetes basics with minikube

### 1. Installation de minikube

- `minikube status` : host, kubelet et apiserver en `Running`, kubeconfig `Configured`.
- `kubectl get nodes` : un seul nœud `minikube` qui porte le rôle `control-plane`.
- `kubectl describe node minikube` : 16 CPU, environ 7,4 Gi de mémoire et 110 pods maximum.

**Que fait `kubectl top pods -A --sort-by cpu --sum=true` ?**
La commande affiche la consommation CPU (en millicores, `m`) et mémoire de tous les pods de tous les namespaces (`-A`). Les pods sont triés du plus consommateur au moins consommateur en CPU (`--sort-by cpu`), et une ligne de total est ajoutée en bas (`--sum=true`). Les données proviennent du metrics-server activé juste avant, ce qui explique qu'il faille attendre environ une minute avant qu'elles soient disponibles. Résultat obtenu : total de 162m CPU et 460Mi de mémoire, avec `kube-apiserver` en tête (68m, 245Mi).

**Composants du namespace `kube-system` :**

| Pod | Rôle |
| --- | --- |
| `kube-apiserver` | Point d'entrée unique du cluster (API REST). `kubectl` et tous les composants passent par lui. |
| `etcd` | Base clé-valeur distribuée qui stocke tout l'état du cluster. |
| `kube-scheduler` | Choisit le nœud sur lequel placer chaque nouveau pod (ressources, contraintes…). |
| `kube-controller-manager` | Exécute les contrôleurs (Deployment, ReplicaSet, Job, Node…) qui ramènent l'état réel vers l'état désiré. |
| `kube-proxy` | Sur chaque nœud, programme les règles réseau (iptables/IPVS) qui implémentent les Services. |
| `coredns` | DNS interne du cluster (`<service>.<namespace>.svc.cluster.local`). |
| `kindnet` | Plugin CNI de minikube : réseau entre les pods. |
| `storage-provisioner` | Crée automatiquement des volumes persistants (addon minikube). |
| `metrics-server` | Collecte CPU et mémoire auprès des kubelets pour `kubectl top` et l'autoscaling. |

### 2. Commandes `kubectl`

- Le pod `kubernetes-bootcamp-…` passe en `1/1 Running`.
- `kubectl logs` affiche `Kubernetes Bootcamp App Started At: … | Running On: <nom du pod>`.
- `kubectl exec $POD_NAME -- cat /etc/os-release` montre que l'image est basée sur **Debian GNU/Linux 8 (jessie)**.
- **2.7** Le shell s'ouvre dans `/`. Le code source se trouve dans **`/server.js`**.
- **2.8** `server.js` contient `www.listen(8080, …)`. L'application écoute donc sur le **port 8080**, et
  `curl localhost:8080` lancé depuis le pod renvoie `Hello Kubernetes bootcamp! | Running on: <pod> | v=1`.
- **2.9** **Non.** Depuis la machine locale, `curl http://10.244.0.4:8080` échoue. L'IP du pod appartient au réseau interne du cluster et n'est pas routée depuis l'hôte. Pour y accéder de l'extérieur, il faut un Service.

### 3. Exposer le service

```bash
kubectl expose deployments/kubernetes-bootcamp --type="NodePort" --port 8080
```

- `kubectl get services` : `kubernetes-bootcamp   NodePort   10.103.27.200   8080:30830/TCP`. Le service est exposé sur le **NodePort 30830**.
- `minikube ip` renvoie `192.168.49.2`.
- `http://192.168.49.2:30830` **ne répond pas**. Avec le driver Docker sous Windows, l'IP du nœud n'est pas joignable depuis l'hôte. Il faut donc ouvrir un tunnel avec `minikube service kubernetes-bootcamp --url`, qui renvoie `http://127.0.0.1:53337`. Ce terminal doit rester ouvert.
- `curl "$APP_URL"` renvoie bien la réponse de l'application.

### 4. Scale up / scale down

- **4.2** On vérifie avec `kubectl get pods` (ou `kubectl get deployments`, colonne READY `5/5`) : 5 pods en `Running`.
- **4.3** Sur 10 requêtes, les réponses viennent de pods différents (`xcrz7`, `ssmtt`, `b7prx`, `hv2nz`…). Le Service répartit la charge : il sélectionne tous les pods portant le label `app=kubernetes-bootcamp`, et kube-proxy distribue chaque nouvelle connexion vers l'un d'eux. Comme la répartition se fait par connexion, un navigateur, qui réutilise la même connexion, tombe toujours sur le même pod.
- **4.4** Après `kubectl scale … --replicas=2`, 3 pods passent en `Terminating` puis disparaissent. Il ne reste que 2 pods `Running`.

### 5. Rolling update et rollback

- **5.3** Pendant `kubectl set image … :v2`, la boucle `curl` (120 requêtes) a donné 8 réponses `v=1` puis 112 réponses `v=2`, **avec 0 erreur**. Le service n'a pas été interrompu. La stratégie `RollingUpdate` (par défaut `maxSurge=25%`, `maxUnavailable=25%`) crée les nouveaux pods et attend qu'ils soient Ready avant de supprimer les anciens. Le Service n'envoie le trafic qu'aux pods Ready.
- **5.5** Avec `:v3` (tag inexistant), le nouveau pod reste en **`ErrImagePull` / `ImagePullBackOff`**, avec l'erreur `docker.io/jocatalin/kubernetes-bootcamp:v3: not found`. Les 2 anciens pods v2 continuent de tourner et **le service répond toujours (`v=2`)**. Comme le nouveau pod ne devient jamais Ready, le rolling update est bloqué et ne supprime pas les anciens réplicas : l'application reste disponible.
- **5.6** `kubectl rollout undo deployments/kubernetes-bootcamp` revient à la révision précédente (v2).
- **5.7** `kubectl rollout history deployments/kubernetes-bootcamp` affiche les révisions 1, 3 et 4. La révision 2 (v2) a été renumérotée en 4 lors du `undo`. La révision 1 correspond à l'image d'origine, d'où :

  ```bash
  kubectl rollout undo deployments/kubernetes-bootcamp --to-revision=1
  ```

  Vérification : l'image est de nouveau `gcr.io/google-samples/kubernetes-bootcamp:v1` et `curl` renvoie `v=1`.

### 6. Déploiement avec des manifests

Les fichiers complétés se trouvent dans `lab-1/deployment.yaml` et `lab-1/service.yaml` :

```yaml
# deployment.yaml
spec:
  replicas: 3 # TO COMPLETE #2
  ...
      containers:
      - name: kubernetes-bootcamp
        image: gcr.io/google-samples/kubernetes-bootcamp:v1 # TO COMPLETE #1
        ports:
        - containerPort: 8080
```

```yaml
# service.yaml
spec:
  type: NodePort
  selector:
    app: kubernetes-bootcamp
  ports:
    - port: 8080
      targetPort: 8080
```

- **6.4** Oui, après `kubectl apply -f deployment.yaml` le pod est `1/1 Running`.
- **6.6** Oui, après `kubectl apply -f service.yaml` (NodePort 30334), l'application répond via `minikube service kubernetes-bootcamp-service --url`.
- **6.8** Avec `replicas: 3`, un `kubectl apply` suffit à mettre le Deployment à jour (approche déclarative). Les 10 requêtes sont réparties sur les 3 réplicas (`pm8jn`, `sgnlj`, `jtdgm`).

### 7. Teardown

`kubectl delete -f service.yaml -f deployment.yaml`. minikube n'a été arrêté qu'à la fin des 3 labs.

---

## Lab 2 – ConfigMap et Secret

### ConfigMaps

| Méthode | Commande | Résultat |
| --- | --- | --- |
| 1. Depuis un fichier | `create configmap pipeline-config --from-file=pipeline-config.properties` | 1 clé (`pipeline-config.properties`) qui contient tout le fichier |
| 2. Depuis des littéraux | `create configmap data-paths --from-literal=…` | 3 clés : `bronze`, `silver`, `gold` |
| 3. Depuis un manifest YAML | `kubectl apply -f configmap-data-platform.yaml` | clés simples et fichiers multi-lignes (`application.yaml`, `table_mappings.csv`) |

La méthode 3 est à privilégier : le manifest est versionnable dans Git (GitOps) et `apply` est idempotent.
`jsonpath='{.data.application\.yaml}'` : le `.` du nom de clé doit être échappé.

### Secrets

- `kubectl get secret … -o yaml` montre des valeurs encodées en base64, par exemple `access-key: QUtJQUlPU0ZPRE5ON0VYQU1QTEU=`.
- Avec `stringData`, on écrit les valeurs en clair dans le manifest et l'API server les encode en base64 lors du stockage dans `data`.
- `… -o jsonpath='{.data.secret-key}' | base64 -d` renvoie `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`, et `jq '@base64d'` décode toutes les clés.

**Conclusion : base64 n'est pas du chiffrement.** Toute personne qui a le droit de lire les Secrets du namespace peut les décoder en une commande. En production, il faut chiffrer etcd au repos, restreindre l'accès via RBAC et ne jamais commiter un Secret en clair (utiliser Sealed Secrets, External Secrets Operator ou Vault).

### Injection dans les pods

| Pod | Mécanisme | Résultat observé |
| --- | --- | --- |
| `spark-app` | `configMapKeyRef` + `envFrom.configMapRef` | `LOG_LEVEL=INFO`, `SPARK_WORKERS=4`, plus `log_level=INFO`, `spark_workers=4` (toutes les clés via `envFrom`) |
| `ceph-connector` | `secretKeyRef` + `envFrom.secretRef` | logs : `Access Key: AKIAIOSFODNN7EXAMPLE` (pod `Succeeded`, `restartPolicy: Never`) |
| `spark-config-reader` | volume `configMap` avec `items` | `/etc/config/application.yaml` et `/etc/config/tables.csv` (clé renommée). Ce sont des liens symboliques vers `..data`, ce qui permet de mettre les fichiers à jour atomiquement |
| `ceph-connector-secure` | volume `secret`, `readOnly`, `defaultMode: 0600` | `/etc/ceph-credentials/s3-credentials.txt` avec les droits `-rw-------` |

Différence entre variables d'environnement et volumes : une variable d'environnement est figée au démarrage du conteneur, alors qu'un fichier monté depuis une ConfigMap ou un Secret est mis à jour automatiquement par le kubelet (sauf avec `subPath`). Le montage en fichier avec des permissions restreintes est aussi plus sûr pour les secrets : les variables d'environnement fuient facilement dans les logs et dans `/proc`.

### Teardown

`kubectl delete namespace lab-configmap-secret` supprime d'un coup tous les objets du namespace.

---

## Lab 3 – Job et CronJob

### 1. Job simple

`data-import-job` : `Complete 1/1` en 6 s. Logs : `Starting data import...` / `Processing 1000 records...` / `Import completed!`

### Job avec retry

**Combien de pods ont été créés ? Pourquoi sont-ils conservés ?**
**4 pods**, tous en `Error` : la tentative initiale plus 3 retries (`backoffLimit: 3`). Le délai entre les tentatives augmente (environ 12 s, 20 s puis 41 s, back-off exponentiel). Avec `restartPolicy: Never`, chaque tentative crée un nouveau pod au lieu de redémarrer le conteneur. Les pods en échec sont conservés pour qu'on puisse consulter leurs logs (`kubectl logs`) et diagnostiquer l'erreur. Ils ne sont supprimés qu'avec le Job (ou via `ttlSecondsAfterFinished`).

**Raison de l'échec dans `describe` :**
`BackoffLimitExceeded`, avec le message « Job has reached the specified backoff limit ». Le statut affiche `0 Succeeded / 4 Failed`.

**Avec `activeDeadlineSeconds: 10` :**
La raison devient **`DeadlineExceeded`** (« Job was active longer than specified deadline »). Un seul pod a été créé : le délai de 10 s a expiré pendant l'attente du back-off, avant le 1er retry. `activeDeadlineSeconds` est prioritaire sur `backoffLimit` : une fois la durée dépassée, le Job est marqué en échec et ses pods actifs sont arrêtés, quel que soit le nombre de retries restants. (Le manifest utilisé est `job-with-retry-deadline10.yaml`.)

### 2. Parallélisation

`batch-export-job` : les 4 pods `batch-export-job-0` à `batch-export-job-3` démarrent à la même seconde (`parallelism: 4`) et le Job termine en `4/4` en 9 s. Avec `completionMode: Indexed`, chaque pod reçoit `JOB_COMPLETION_INDEX` (0 à 3) et traite son propre shard (`users with id % 4 == N`). Le nom du pod contient aussi l'index. `ttlSecondsAfterFinished: 600` supprime le Job 10 minutes après la fin.

### 3. CronJob

- `bronze-to-silver-pipeline` (`*/2 * * * *`) a créé automatiquement le Job `bronze-to-silver-pipeline-29867898`. Le suffixe correspond à l'heure planifiée, exprimée en minutes depuis l'epoch. Logs : `Bronze→Silver ETL started...` puis `Completed! 500 records processed`.
- `concurrencyPolicy: Forbid` empêche de lancer une nouvelle exécution si la précédente tourne encore.
- `successfulJobsHistoryLimit: 3` / `failedJobsHistoryLimit: 1` limitent le nombre de Jobs terminés conservés.
- `daily-backup` : `0 2 * * *` avec `timeZone: Europe/Paris`, la colonne TIMEZONE l'affiche. Sans `timeZone`, l'horaire suit le fuseau du controller-manager (souvent UTC).

### 4. Monitoring

- `kubectl get jobs` / `describe job` / `logs -l job-name=…` permettent de suivre les Jobs.
- `kubectl patch cronjob … -p '{"spec":{"suspend":true}}'` passe la colonne `SUSPEND` à `True`. Plus aucun Job n'est créé tant que le CronJob n'est pas réactivé avec `suspend:false`.

### 5. Scénario pipeline

- La ConfigMap `etl-config` (`BATCH_SIZE`, `SOURCE_LAYER`, `TARGET_LAYER`) est injectée via `envFrom` dans le CronJob `etl-bronze-to-silver` (`*/5`). Le CronJob déclare aussi des `requests`/`limits` CPU et mémoire.
- Test sans attendre la planification : `kubectl create job etl-manual-run --from=cronjob/etl-bronze-to-silver`. Logs : `ETL: bronze -> silver`, `Batch size: 1000`, …, `Completed!`
- Intérêt : on modifie les paramètres du pipeline dans la ConfigMap sans reconstruire l'image ni modifier le CronJob.

### Teardown

Jobs et CronJobs supprimés, puis le namespace. `kubectl get namespace lab-job-cronjob` renvoie bien `NotFound`. Pour finir, `minikube stop`.
