function scrollToBottom() {
  const messagesContainer = document.getElementById("messages-container");
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addSQLResponse(sql, results) {
  const messagesContainer = document.getElementById("messages-container");
  const messageDiv = document.createElement("div");
  messageDiv.className = "message message-assistant";

  let resultsHtml = "";

  if (typeof results === "string") {
    resultsHtml += sql;
    sql = "";
  }
  if (results && results.length > 0 && typeof results === "object") {
    const columns = Object.keys(results[0]);
    resultsHtml += `
    <div class="results-table-container" style="margin-top: 1rem; overflow-x: auto;">
    <table class="results-table">
    <thead>
    <tr>
      ${columns.map((col) => `<th>${col}</th>`).join("")}
    </tr>
    </thead>
    <tbody>
 ${results
   .map(
     (row) => `
   <tr>
     ${columns
       .map((col) => `<td>${row[col] !== null ? row[col] : "NULL"}</td>`)
       .join("")}
   </tr>
 `
   )
   .join("")}
</tbody>
</table>
</div>`;
  }

  messageDiv.innerHTML = `
           <div class="message-avatar">
               <i class="fas fa-robot"></i>
           </div>
           <div class="message-content">
               <div class="message-bubble">
                  ${
                    sql.trim() != ""
                      ? `<div class="sql-block">${sql}</div>`
                      : ""
                  }
                   ${resultsHtml}
               </div>
               <div class="message-meta">
                   <span class="timestamp">${new Date().toLocaleTimeString([], {
                     hour: "2-digit",
                     minute: "2-digit",
                   })}</span>
               </div>
           </div>
       `;

  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
function insertPrompt(prompt) {
  textarea.value = prompt;
  textarea.focus();
  textarea.dispatchEvent(new Event("input"));
}

const textarea = document.getElementById("user-input");
textarea.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

function addMessage(content, sender) {
  const messagesContainer = document.getElementById("messages-container");
  const messageDiv = document.createElement("div");
  messageDiv.className = `message message-${sender}`;

  const avatarIcon = sender === "user" ? "fa-user" : "fa-robot";

  messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${avatarIcon}"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">${content}</div>
                <div class="message-meta">
                    <span class="timestamp">${new Date().toLocaleTimeString(
                      [],
                      { hour: "2-digit", minute: "2-digit" }
                    )}</span>
                </div>
            </div>
        `;

  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showLoadingSteps() {
  const container = document.getElementById("messages-container");

  const loadingHTML = document.createElement("div");
  loadingHTML.className = "loading-state";
  loadingHTML.id = "loading-state";
  loadingHTML.innerHTML = `
      <div class="loading-step">
        <div class="loading-step-icon active"><i class="fas fa-brain"></i></div>
        <div class="loading-step-content">
          <div class="loading-step-title">Thinking</div>
          <div class="loading-step-description">Analyzing your request...</div>
        </div>
      </div>
      <div class="loading-step">
        <div class="loading-step-icon inactive"><i class="fas fa-database"></i></div>
        <div class="loading-step-content">
          <div class="loading-step-title">Extracting database schema</div>
          <div class="loading-step-description">Reading tables and relationships...</div>
        </div>
      </div>
      <div class="loading-step">
        <div class="loading-step-icon inactive"><i class="fas fa-code"></i></div>
        <div class="loading-step-content">
          <div class="loading-step-title">Creating SQL</div>
          <div class="loading-step-description">Formulating SQL query...</div>
        </div>
      </div>
      <div class="loading-step">
        <div class="loading-step-icon inactive"><i class="fas fa-terminal"></i></div>
        <div class="loading-step-content">
          <div class="loading-step-title">Executing query</div>
          <div class="loading-step-description">Running the query on your database...</div>
        </div>
      </div>
    `;

  container.appendChild(loadingHTML);
  scrollToBottom();

  const steps = loadingHTML.querySelectorAll(".loading-step-icon");
  let current = 0;

  const interval = setInterval(() => {
    if (current > 0) steps[current - 1].classList.remove("active");
    if (current >= steps.length) {
      clearInterval(interval);
      return;
    }
    steps[current].classList.remove("inactive");
    steps[current].classList.add("active");
    current++;
  }, 2500);
}

// Function to remove loading bubble
function removeLoadingSteps() {
  const loading = document.getElementById("loading-state");
  if (loading) loading.remove();
}

document.getElementById("clear-chat").addEventListener("click", function () {
  const messagesContainer = document.getElementById("messages-container");
  messagesContainer.innerHTML = `
           <div class="message message-assistant">
               <div class="message-avatar">
                   <i class="fas fa-robot"></i>
               </div>
               <div class="message-content">
                   <div class="message-bubble">
                       Hi! I'm your AI SQL assistant. Ask me anything about your data in plain English, and I'll generate and run the SQL queries for you.
                       <div class="quick-prompts">
                           <div class="quick-prompt" onclick="insertPrompt('Show me the top 5 customers by revenue')">Top customers</div>
                           <div class="quick-prompt" onclick="insertPrompt('What were our best selling products last month?')">Best sellers</div>
                           <div class="quick-prompt" onclick="insertPrompt('Find customers who haven\\'t ordered in 3 months')">Inactive customers</div>
                       </div>
                   </div>
                   <div class="message-meta">
                       <span class="timestamp">Just now</span>
                   </div>
               </div>
           </div>
       `;
});

document
  .getElementById("chat-form")
  .addEventListener("submit", async function (e) {
    e.preventDefault();
    const userInput = textarea.value.trim();

    if (!userInput) return;

    // Add user message to chat
    addMessage(userInput, "user");
    textarea.value = "";
    textarea.style.height = "auto";

    showLoadingSteps();
    try {
      const response = await fetch("http://localhost:3000/api/agent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: userInput }),
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const data = await response.json();

      removeLoadingSteps();

      if (data.response && data.generated_sql) {
        addSQLResponse(data.generated_sql, data.response);
      } else {
        // Handle unexpected response format
        addMessage(
          "Received response in unexpected format. Please try again.",
          "assistant"
        );
      }
    } catch (error) {
      removeLoadingSteps();
      addMessage(
        "Sorry, I encountered an error processing your request. Please try again.",
        "assistant"
      );
      console.log(error.message);
    }
  });
