const express = require("express")
const cors = require('cors')
const bodyparser = require('body-parser');
const PORT = 3000
const app = express();

app.use(cors())
app.use(bodyparser.json())


const { spawn } = require("child_process");

app.post("/api/agent",async(req,res)=>{
try {
    const {message} = req.body;
    
    if(!message || message.trim()=='') return res.status(401).json("need user message")
    
     const python = spawn("python3", ["./childProcess/sqlAgentProcess.py", message]);

      let result = "";
      python.stdout.on("data", (data) => {
        result += data.toString();
      });

      python.stderr.on("data", (data) => {
        console.error("Python Error:", data.toString());
      });

      python.on("close", (code) => {
      try {
        
        let parsed = JSON.parse(result);
        
        if (parsed.response.trim().startsWith("[")) {
          parsed_response = JSON.parse(parsed.response);
        
         
          
          return res
          .status(200)
          .json({
            response: parsed_response,
            generated_sql: parsed.generated_sql,
          });
        }
        
        return res.status(200).json(parsed);    
      } catch (error) {
        return res.status(501).json({
          error:"Sorry, something went wrong. Please try again."
        })
      }
      });
} catch (error) {
    res.status(501).json(error.message)
}
})


app.listen(PORT,(req,res)=>{
    console.log(`Server is running at http://localhost:${PORT}`);  
})