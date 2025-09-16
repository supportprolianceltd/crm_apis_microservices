import swaggerJsdoc from "swagger-jsdoc";
import swaggerUi from "swagger-ui-express";
import env from "dotenv";

env.config();

const options = {
  definition: {
    openapi: "3.0.0",
    info: {
      title: "Messaging Service API",
      version: "1.0.0",
      description: "API documentation for the Messaging Service",
    },
    servers: [
      {
        url: `http://localhost:${process.env.PORT}`,
        description: "Development server",
      },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "JWT",
        },
      },
    },
  },
  apis: ["./src/routes/*.js", "./src/api/**/*.js"], // Path to the API routes
};

const specs = swaggerJsdoc(options);

const swaggerDocs = (app) => {
  // Swagger page
  app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(specs));

  // Docs in JSON format
  app.get("/docs.json", (req, res) => {
    res.setHeader("Content-Type", "application/json");
    res.send(specs);
  });

  console.log(
    `📚 Docs available at http://localhost:${process.env.PORT}/api-docs`
  );
};

export default swaggerDocs;
