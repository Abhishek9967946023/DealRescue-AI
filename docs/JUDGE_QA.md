# Judge Q&A

### Why Hindsight?
Because the agent needs persistent experience, not just conversation history. A sales outcome becomes future decision evidence.

### What is innovative?
The system learns from both successful and failed interventions. It can recommend what to do and what not to repeat.

### Why not a normal vector database?
A retrieval store can return documents. DealRescue is designed around experience: what happened, what action was tried, and what outcome followed. Hindsight is used for the memory operations that drive the agent.

### How do you prove improvement?
The demo shows a before/after recommendation, positive/negative outcome evidence, and a retained deal autopsy that becomes future memory.

### What happens when memory is weak?
The system falls back to local evidence and explicitly indicates the evidence source instead of inventing facts.

### Why Sales & Revenue?
Enterprise deals are full of repeated objections and tacit knowledge. A seller's best lessons are often buried in old deals and lost when people change teams.

### What is the core metric?
For a production deployment, measure recommendation quality and deal progression against a no-memory baseline. The included UI starts with positive/negative outcome signals as a demo metric.
